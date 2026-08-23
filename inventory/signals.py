from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StockMovement_model
from .usecases.recompute_product_status import recompute_product_status
from .usecases.check_low_stock_alert import check_low_stock_and_notify


@receiver(post_save, sender=StockMovement_model)
def recompute_status_on_stock_movement(sender, instance, **kwargs):
    """
    Every stock movement (purchase entry, manual reduction, checkout sale)
    changes a variant's current stock, so the product's status needs to be
    recalculated from the fresh totals every time one is created.
    """
    recompute_product_status(instance.product_variant.product_id)
    check_low_stock_and_notify(instance.product_variant_id)
