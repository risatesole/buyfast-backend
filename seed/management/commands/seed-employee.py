import random

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import EmployeePosition, Profile, User, employee_model

DEFAULT_EMPLOYEE_COUNT = 25
EMPLOYEE_PASSWORD = "Employee@12345"
EMAIL_DOMAIN = "buyfast-demo.com"

# Reused across runs to build deterministic, idempotent emails
# (seed-employee-000@..., seed-employee-001@..., ...) so re-running the
# command doesn't create duplicate employees — it just leaves existing ones
# alone (see get_or_create below).
FIRST_NAMES = [
    "Carlos", "Maria", "Juan", "Ana", "Luis", "Carmen", "Miguel", "Rosa",
    "Jose", "Laura", "Pedro", "Sofia", "Manuel", "Elena", "Rafael", "Patricia",
    "Diego", "Gabriela", "Fernando", "Valentina", "Ricardo", "Camila", "Alberto",
    "Isabel", "Francisco", "Daniela", "Eduardo", "Andrea", "Roberto", "Lucia",
]

LAST_NAMES = [
    "Perez", "Gonzalez", "Rodriguez", "Fernandez", "Lopez", "Martinez",
    "Sanchez", "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz",
    "Reyes", "Morales", "Cruz", "Ortiz", "Gutierrez", "Chavez", "Ramos",
    "Vargas", "Castillo", "Jimenez", "Mendoza", "Rojas", "Herrera", "Medina",
]


class Command(BaseCommand):
    help = "Seed demo employees spread across every position and profile"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_EMPLOYEE_COUNT,
            help=f"Number of employees to create (default: {DEFAULT_EMPLOYEE_COUNT})",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]

        self.stdout.write(self.style.WARNING(f"\n=== Seeding {count} Demo Employees ===\n"))

        positions = [choice[0] for choice in EmployeePosition.choices]
        if not positions:
            self.stdout.write(self.style.ERROR("  No EmployeePosition choices found. Aborting."))
            return

        profiles = list(Profile.objects.all())
        if not profiles:
            self.stdout.write(
                self.style.WARNING(
                    "  No Profile records found — employees will be created without a "
                    "profile. Run migrations (accounts 0006_seed_profiles) or the `seed` "
                    "command first if you want profiles assigned."
                )
            )

        created_count = 0
        existing_count = 0

        for i in range(count):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            email = f"seed-employee-{i:03d}@{EMAIL_DOMAIN}"
            position = positions[i % len(positions)]
            profile = random.choice(profiles) if profiles else None

            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "employee",
                    "status": "active",
                    "is_staff": True,
                    "is_email_verified": True,
                    "phone_number": f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}",
                },
            )
            if user_created:
                user.set_password(EMPLOYEE_PASSWORD)
                user.save()

            employee, employee_created = employee_model.objects.get_or_create(
                user=user,
                defaults={
                    "position": position,
                    "profile": profile,
                    "is_active": True,
                },
            )

            if user_created or employee_created:
                created_count += 1
                profile_label = profile.name if profile else "—"
                self.stdout.write(
                    f"  {user.email} — created ({position}, profile={profile_label})"
                )
            else:
                existing_count += 1

        self.stdout.write(self.style.SUCCESS(f"\n✓ Done. {created_count} created, {existing_count} already existed.\n"))
        self.stdout.write(f"  Login password for all seeded employees: {EMPLOYEE_PASSWORD}\n")
