from ..models import StockMovement_model
from products.default.models import ProductVariant

def create_initial_inventory(product_variant_id, quantity, date_time=None):
    """
    Creates the initial inventory record for a product.

    date_time is optional and only meant for backdating this movement (e.g.
    demo/seed data that should look like it was stocked in the past) — real
    callers should omit it and let it default to the row's auto_now_add
    creation time.
    """
    product_variant = ProductVariant.objects.get(id=product_variant_id)

    movement = StockMovement_model.objects.create(
        product_variant=product_variant,
        movement_type="initial_inventory",
        quantity=quantity,
        balance=quantity,
        document_reference = f"Initial inventory sir. todo create document of reference based in user credentials"
    )

    if date_time is not None:
        StockMovement_model.objects.filter(pk=movement.pk).update(date_time=date_time)
