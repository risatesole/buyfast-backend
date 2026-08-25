import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from inventory.models import StockDecrease_model, StockEntry_model, StockMovement_model
from inventory.queries import get_variant_current_stock
from products.default.models import ProductVariant

DEFAULT_VARIANT_COUNT = 10

# Weighted so the targeted variants read as a realistic mix once this
# command is done: most restocked and healthy, but enough left low/empty
# for the admin dashboard's low-stock widget to actually have something to
# show. "low_stock"/"out_of_stock" variants deliberately get no purchase
# entry at all — they're the ones "left without filling".
PROFILE_WEIGHTS = [
    ("restocked", 0.4),
    ("low_stock", 0.35),
    ("out_of_stock", 0.25),
]

PURCHASE_REASONS = [
    "Reposición de stock del proveedor habitual",
    "Compra adicional por alta demanda",
    "Reabastecimiento programado",
    "Ingreso de nuevo lote de mercancía",
]

DECREASE_REASONS = [
    "Producto dañado en almacén",
    "Conteo físico - faltante detectado",
    "Ajuste de inventario",
    "Mercancía vencida o fuera de circulación",
    "Devolución al proveedor",
]


def _pick_profile():
    roll = random.random()
    cumulative = 0.0
    for profile, weight in PROFILE_WEIGHTS:
        cumulative += weight
        if roll <= cumulative:
            return profile
    return PROFILE_WEIGHTS[-1][0]


def _advance(cursor, now):
    """
    Moves `cursor` forward by a random fraction of whatever room is left
    before `now`, so it always makes forward progress no matter how little
    time remains — a fixed hours-based step would often overshoot `now`
    outright for a variant whose latest movement already sits close to it
    (very likely here, since seed-orders.py spreads order dates all the way
    up through today), silently producing zero events instead.
    """
    remaining = now - cursor
    if remaining <= timedelta(seconds=1):
        return now
    return cursor + remaining * random.uniform(0.15, 0.6)


def _latest_movement_time(variant_id):
    latest = (
        StockMovement_model.objects
        .filter(product_variant_id=variant_id)
        .order_by("-date_time", "-id")
        .first()
    )
    return latest.date_time if latest else None


def _create_purchase_entry(variant, employee, quantity, when):
    """Mirrors StockMovementListView.post's purchase_entry flow."""
    current_balance = get_variant_current_stock(variant.id)
    new_balance = current_balance + quantity
    reason = random.choice(PURCHASE_REASONS)

    movement = StockMovement_model.objects.create(
        product_variant=variant,
        movement_type="purchase_entry",
        quantity=quantity,
        balance=new_balance,
        document_reference=reason,
    )
    # Backdate after creation (like seed-orders.py) so this reads as having
    # happened over the past few days instead of at the exact moment this
    # command ran — auto_now_add always stamps "now" first.
    StockMovement_model.objects.filter(pk=movement.pk).update(date_time=when)
    StockEntry_model.objects.create(stock_movement=movement, created_by=employee, reason=reason)


def _create_manual_decrease(variant, employee, quantity, when):
    """Mirrors StockMovementDecreaseView.post's manual_decrease flow."""
    current_balance = get_variant_current_stock(variant.id)
    new_balance = current_balance - quantity
    reason = random.choice(DECREASE_REASONS)

    movement = StockMovement_model.objects.create(
        product_variant=variant,
        movement_type="manual_decrease",
        quantity=quantity,
        balance=new_balance,
        document_reference="",
    )
    StockMovement_model.objects.filter(pk=movement.pk).update(date_time=when)
    StockDecrease_model.objects.create(stock_movement=movement, decreased_by=employee, reason=reason)


class Command(BaseCommand):
    help = (
        "Simulates employees manually adjusting stock (purchase entries and manual "
        "decreases) on the most recently added product variants — some end up "
        "restocked/healthy, some are deliberately left low or fully depleted so the "
        "admin dashboard's low-stock widget has real data to show."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_VARIANT_COUNT,
            help=f"How many of the most recently added variants to target (default: {DEFAULT_VARIANT_COUNT})",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]

        employees = list(User.objects.filter(role="employee"))
        if not employees:
            self.stdout.write(
                self.style.ERROR("  No employee accounts found. Run `seed` (and optionally `seed-employee`) first.")
            )
            return

        variants = list(ProductVariant.objects.select_related("product").order_by("-created_at")[:count])
        if not variants:
            self.stdout.write(self.style.ERROR("  No ProductVariant records found. Run `seed` first."))
            return

        self.stdout.write(
            self.style.WARNING(f"\n=== Simulating employee stock activity on the last {len(variants)} variants ===\n")
        )

        now = timezone.now()

        for variant in variants:
            profile = _pick_profile()
            # Each variant's simulated activity walks forward in time from
            # wherever its real movement history currently ends, so it never
            # collides with (or predates) whatever seed/seed-orders already
            # recorded for it — same chronological-safety approach as
            # seed-orders.py.
            cursor = _latest_movement_time(variant.id) or (now - timedelta(days=14))

            if profile == "restocked":
                event_count = random.randint(1, 3)
                events_made = 0
                for _ in range(event_count):
                    cursor = _advance(cursor, now)
                    if cursor >= now:
                        break
                    quantity = random.randint(20, 80)
                    _create_purchase_entry(variant, random.choice(employees), quantity, cursor)
                    events_made += 1
                final_balance = get_variant_current_stock(variant.id)
                self.stdout.write(f"  {variant.sku} — restocked ({events_made} entries), balance now {final_balance}")
                continue

            # low_stock / out_of_stock: no purchase entries at all — this
            # variant is deliberately "left without filling" — only manual
            # decreases, draining it down to a small remainder or to zero.
            current_balance = get_variant_current_stock(variant.id)
            target_balance = 0 if profile == "out_of_stock" else random.randint(1, min(4, max(1, current_balance)))
            remaining = max(0, current_balance - target_balance)

            events_made = 0
            if remaining > 0:
                event_count = random.randint(1, 3)
                for i in range(event_count):
                    cursor = _advance(cursor, now)
                    if cursor >= now or remaining <= 0:
                        break
                    is_last = i == event_count - 1
                    quantity = remaining if is_last else random.randint(1, max(1, remaining - 1))
                    quantity = min(quantity, remaining)
                    if quantity <= 0:
                        break
                    _create_manual_decrease(variant, random.choice(employees), quantity, cursor)
                    remaining -= quantity
                    events_made += 1

            final_balance = get_variant_current_stock(variant.id)
            # Label off the actual resulting balance rather than the profile
            # rolled at the start — a variant that was already at 0 before
            # this command touched it should read as "out of stock", not
            # "low stock", even if "low_stock" was the profile picked for it.
            label = "out of stock" if final_balance <= 0 else "low stock"
            self.stdout.write(f"  {variant.sku} — left {label} ({events_made} decreases), balance now {final_balance}")

        self.stdout.write(self.style.SUCCESS("\nDone.\n"))
