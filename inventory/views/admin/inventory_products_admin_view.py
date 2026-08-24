from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from products.default.models import ProductVariant
from inventory.serializers import ProductInventorySerializer
from inventory.queries import annotate_variant_stock, apply_admin_inventory_filters, get_variant_current_stock
from api.permissions import permission_required

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class CustomLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 20
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100

class AdminProductInventoryListView(generics.ListAPIView):
    """
    Admin view to list all products with their inventory quantities.
    Shows product name, description, thumbnail, and current quantity.
    
    Query Parameters:
    - category: Filter by product category
    - status: Filter by variant status (true/false)
    - search: Search by product name, variant name, or SKU
    - min_quantity: Filter by minimum quantity
    - max_quantity: Filter by maximum quantity
    - inventory_status: Filter by inventory status (in_stock, low_stock, out_of_stock, medium_stock)
    - ordering: Order by field (name, sku, quantity, created_at, selling_price)
    - page: Page number (for page-based pagination)
    - page_size: Number of items per page (for page-based pagination)
    - offset: Number of items to skip (for offset-based pagination)
    - limit: Number of items to return (for offset-based pagination)
    """
    serializer_class = ProductInventorySerializer
    pagination_class = CustomLimitOffsetPagination
    permission_classes = [permission_required("inventory.view")]

    def get_queryset(self):
        # Annotate with total quantity
        queryset = ProductVariant.objects.all().select_related('product').prefetch_related('images')

        # Annotate with quantity for filtering and ordering (shared helper, see inventory/queries.py)
        queryset = annotate_variant_stock(queryset)

        # Filters + ordering (shared with the admin inventory report/export view)
        queryset = apply_admin_inventory_filters(queryset, self.request)

        return queryset

class AdminProductInventoryDetailView(generics.RetrieveUpdateAPIView):
    """
    Admin view to get and update inventory details for a specific product variant.
    """
    queryset = ProductVariant.objects.all().select_related('product').prefetch_related('images')
    serializer_class = ProductInventorySerializer
    lookup_field = 'pk'

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [permission_required("products.edit")()]
        return [permission_required("inventory.view")()]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Update variant status if provided
        if 'status' in request.data:
            instance.status = request.data['status']
            instance.save()
        
        # Update selling price if provided
        if 'selling_price' in request.data:
            instance.selling_price = request.data['selling_price']
            instance.save()
        
        return super().update(request, *args, **kwargs)

class AdminLowStockView(generics.ListAPIView):
    """
    Admin view to list products with low stock (quantity below threshold).
    
    Query Parameters:
    - threshold: Stock threshold (default: 10)
    - offset: Number of items to skip
    - limit: Number of items to return
    """
    serializer_class = ProductInventorySerializer
    pagination_class = CustomLimitOffsetPagination
    permission_classes = [permission_required("inventory.view")]

    def get_queryset(self):
        threshold = int(self.request.query_params.get('threshold', 10))
        
        # Get all variants with their stock quantities
        variants = ProductVariant.objects.all().select_related('product').prefetch_related('images')
        
        # Filter those with stock below threshold
        low_stock_variants = []
        for variant in variants:
            quantity = self.get_variant_quantity(variant)
            if 0 < quantity < threshold:
                low_stock_variants.append(variant)
        
        return low_stock_variants
    
    def get_variant_quantity(self, variant):
        return get_variant_current_stock(variant.id)

class AdminOutOfStockView(generics.ListAPIView):
    """
    Admin view to list products that are out of stock.
    
    Query Parameters:
    - offset: Number of items to skip
    - limit: Number of items to return
    """
    serializer_class = ProductInventorySerializer
    pagination_class = CustomLimitOffsetPagination
    permission_classes = [permission_required("inventory.view")]

    def get_queryset(self):
        variants = ProductVariant.objects.all().select_related('product').prefetch_related('images')

        out_of_stock_variants = []
        for variant in variants:
            quantity = self.get_variant_quantity(variant)
            if quantity == 0:
                out_of_stock_variants.append(variant)
        
        return out_of_stock_variants
    
    def get_variant_quantity(self, variant):
        return get_variant_current_stock(variant.id)

class AdminInventorySummaryView(APIView):
    """
    Admin view to get inventory summary statistics, aggregated across every
    variant in the database (not just one paginated page).

    Computed live via a single aggregate query on each request, so it always
    reflects the latest stock movements (sales, inventory entries/decreases,
    etc.) with no separate table to keep in sync.
    """
    permission_classes = [permission_required("inventory.view")]

    def get(self, request):
        queryset = annotate_variant_stock(ProductVariant.objects.all())

        value_expression = ExpressionWrapper(
            F('total_quantity') * F('selling_price'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )

        totals = queryset.aggregate(
            total_variants=Count('id'),
            total_items_in_stock=Coalesce(Sum('total_quantity'), Value(0)),
            total_inventory_value=Coalesce(
                Sum(value_expression),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            out_of_stock_count=Count('id', filter=Q(total_quantity__lte=0)),
            # Mirrors ProductInventorySerializer.get_below_minimum_stock: each
            # variant's own minimum_stock alert threshold (0 = alert disabled).
            low_stock_count=Count(
                'id',
                filter=Q(
                    total_quantity__gt=0,
                    minimum_stock__gt=0,
                    total_quantity__lte=F('minimum_stock'),
                ),
            ),
        )

        total_products = ProductVariant.objects.values('product').distinct().count()

        return Response({
            'total_variants': totals['total_variants'],
            'total_products': total_products,
            'total_items_in_stock': totals['total_items_in_stock'],
            'total_inventory_value': round(float(totals['total_inventory_value']), 2),
            'low_stock_count': totals['low_stock_count'],
            'out_of_stock_count': totals['out_of_stock_count'],
        })

class AdminBulkInventoryUpdateView(APIView):
    """
    Admin view to bulk update inventory status.
    """
    permission_classes = [permission_required("products.edit")]
    
    def post(self, request):
        variant_ids = request.data.get('variant_ids', [])
        action = request.data.get('action')  # 'activate' or 'deactivate'
        
        if not variant_ids or not action:
            return Response(
                {'error': 'variant_ids and action are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if action not in ['activate', 'deactivate']:
            return Response(
                {'error': 'action must be "activate" or "deactivate"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        status_bool = action == 'activate'
        updated = ProductVariant.objects.filter(id__in=variant_ids).update(status=status_bool)
        
        return Response({
            'message': f'Successfully updated {updated} variants',
            'updated_count': updated
        })
