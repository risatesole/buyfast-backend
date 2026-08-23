from django.db.models import Q

from accounts.models import Profile, User
from notifications.emailing import send_low_stock_alert_email
from products.default.models import ProductVariant

from ..queries import get_variant_current_stock


def check_low_stock_and_notify(variant_id):
    """
    Compares a variant's current stock against its configured minimum_stock
    and emails every employee holding the 'inventory.manage' permission the
    first time it dips at/below that threshold. Stays quiet on further
    movements while it's still low, and re-arms once restocked above the
    minimum, so a variant that dips again later alerts again.
    """
    try:
        variant = ProductVariant.objects.select_related("product").get(pk=variant_id)
    except ProductVariant.DoesNotExist:
        return

    if variant.minimum_stock <= 0:
        return

    current_stock = get_variant_current_stock(variant_id)

    if current_stock <= variant.minimum_stock:
        if not variant.low_stock_notified:
            ProductVariant.objects.filter(pk=variant_id).update(low_stock_notified=True)
            _notify_stock_managers(variant, current_stock)
    elif variant.low_stock_notified:
        ProductVariant.objects.filter(pk=variant_id).update(low_stock_notified=False)


def _notify_stock_managers(variant, current_stock):
    recipient_profile_ids = [
        profile.id
        for profile in Profile.objects.all()
        if "inventory.manage" in (profile.permissions or [])
    ]

    # Superusers implicitly hold every permission (see has_permission() in
    # api/permissions.py) but usually have no employee_profile/Profile row
    # (e.g. accounts created via `manage.py createsuperuser`), so they must
    # be included explicitly rather than via the employee_profile join below.
    recipients = User.objects.filter(
        Q(is_superuser=True)
        | Q(
            employee_profile__profile_id__in=recipient_profile_ids,
            employee_profile__is_active=True,
        ),
        is_active=True,
    ).distinct()

    for user in recipients:
        send_low_stock_alert_email(
            to_email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            product_name=variant.product.name,
            variant_name=variant.name,
            sku=variant.sku,
            current_stock=current_stock,
            minimum_stock=variant.minimum_stock,
        )
