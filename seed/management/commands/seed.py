from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import PERMISSION_CODES, EmployeePosition, Profile, User, employee_model
from inventory.inventory import create_initial_inventory
from products.default.models import Category, Product, ProductImage, ProductVariant

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "blue"
ADMIN_FIRST_NAME = "Admin"
ADMIN_LAST_NAME = "Admin"


def _gallery(image_urls, alt_text):
    """
    Builds a variant's image set from at least 3 distinct source photos —
    one each for HERO, GALLERY, and DETAIL — plus a LIFESTYLE crop (reusing
    the gallery photo) and a THUMBNAIL crop (reusing the hero photo, since
    that's the row the repository pulls out separately for
    ProductVariant.thumbnail).
    """
    hero_url, gallery_url, detail_url = image_urls[0], image_urls[1], image_urls[2]

    return [
        {"image": f"{hero_url}?w=800&h=800&fit=crop", "image_type": "HERO", "alt_text": alt_text, "order": 0},
        {"image": f"{gallery_url}?w=800&h=600&fit=crop", "image_type": "GALLERY", "alt_text": alt_text, "order": 1},
        {"image": f"{detail_url}?w=600&h=600&fit=crop", "image_type": "DETAIL", "alt_text": alt_text, "order": 2},
        {"image": f"{gallery_url}?w=750&h=500&fit=crop", "image_type": "LIFESTYLE", "alt_text": alt_text, "order": 3},
        {"image": f"{hero_url}?w=200&h=200&fit=crop", "image_type": "THUMBNAIL", "alt_text": alt_text, "order": 4},
    ]


# Each entry mirrors the Product -> ProductVariant -> ProductImage shape:
# one product, its variant(s), and each variant's image(s), all in one JSON-like
# block — the 3 source photos for a variant live right next to that variant,
# in its own "images" list, instead of in a separate lookup table.
PRODUCTS = [
    {
        "name": "Cuaderno Universitario 100 Hojas",
        "slug": "cuaderno-universitario-100-hojas",
        "category_slug": "papeleria",
        "thumbnail": "https://images.unsplash.com/photo-1531346878377-a5be20888e57?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Cuaderno Universitario 100 Hojas - Rayado",
                "description": "Cuaderno universitario de 100 hojas rayadas, ideal para tomar apuntes en clase.",
                "attribute": "Rayado",
                "variantnumber": 1,
                "slug": "cuaderno-universitario-100-hojas-rayado",
                "sku": "PAP-CUAD-001",
                "selling_price": "150.00",
                "tax_rate": "0.18",
                "minimum_stock": 10,
                "initial_stock": 50,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1531346878377-a5be20888e57",
                        "https://images.unsplash.com/photo-1517842645767-c639042777db",
                        "https://images.unsplash.com/photo-1568205612837-017257d2310a",
                    ],
                    "Cuaderno universitario de 100 hojas rayado",
                ),
            },
            {
                "name": "Cuaderno Universitario 100 Hojas - Cuadriculado",
                "description": "Cuaderno universitario de 100 hojas cuadriculadas, útil para materias de ciencias y matemáticas.",
                "attribute": "Cuadriculado",
                "variantnumber": 2,
                "slug": "cuaderno-universitario-100-hojas-cuadriculado",
                "sku": "PAP-CUAD-002",
                "selling_price": "150.00",
                "tax_rate": "0.18",
                "minimum_stock": 10,
                "initial_stock": 45,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1531346878377-a5be20888e57",
                        "https://images.unsplash.com/photo-1517842645767-c639042777db",
                        "https://images.unsplash.com/photo-1568205612837-017257d2310a",
                    ],
                    "Cuaderno universitario de 100 hojas cuadriculado",
                ),
            },
        ],
    },
    {
        "name": "Set de Bolígrafos Punta Fina",
        "slug": "set-boligrafos-punta-fina",
        "category_slug": "papeleria",
        "thumbnail": "https://images.unsplash.com/photo-1568051243858-533a607809a5?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Set de Bolígrafos Punta Fina - Azul y Negro",
                "description": "Set de bolígrafos de punta fina en tinta azul y negra, escritura suave y precisa.",
                "attribute": "Azul y Negro",
                "variantnumber": 1,
                "slug": "set-boligrafos-punta-fina-azul-negro",
                "sku": "PAP-BOLI-001",
                "selling_price": "95.00",
                "tax_rate": "0.18",
                "minimum_stock": 15,
                "initial_stock": 60,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1568051243858-533a607809a5",
                        "https://images.unsplash.com/photo-1495364141860-b0d03eccd065",
                        "https://images.unsplash.com/photo-1455390582262-044cdead277a",
                    ],
                    "Set de bolígrafos punta fina azul y negro",
                ),
            },
            {
                "name": "Set de Bolígrafos Punta Fina - Rojo y Verde",
                "description": "Set de bolígrafos de punta fina en tinta roja y verde, ideal para correcciones y anotaciones.",
                "attribute": "Rojo y Verde",
                "variantnumber": 2,
                "slug": "set-boligrafos-punta-fina-rojo-verde",
                "sku": "PAP-BOLI-002",
                "selling_price": "95.00",
                "tax_rate": "0.18",
                "minimum_stock": 15,
                "initial_stock": 55,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1568051243858-533a607809a5",
                        "https://images.unsplash.com/photo-1495364141860-b0d03eccd065",
                        "https://images.unsplash.com/photo-1455390582262-044cdead277a",
                    ],
                    "Set de bolígrafos punta fina rojo y verde",
                ),
            },
        ],
    },
    {
        "name": "Manual de Laboratorio de Anatomía",
        "slug": "manual-laboratorio-anatomia",
        "category_slug": "libros_manuales",
        "thumbnail": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Manual de Laboratorio de Anatomía - Edición 2024",
                "description": "Manual de laboratorio de anatomía, edición 2024, con guías prácticas para las sesiones de disección.",
                "attribute": "Edición 2024",
                "variantnumber": 1,
                "slug": "manual-laboratorio-anatomia-2024",
                "sku": "LIB-ANAT-001",
                "selling_price": "850.00",
                "tax_rate": "0.00",
                "minimum_stock": 5,
                "initial_stock": 20,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1544947950-fa07a98d237f",
                        "https://images.unsplash.com/photo-1481627834876-b7833e8f5570",
                        "https://images.unsplash.com/photo-1512820790803-83ca734da794",
                    ],
                    "Manual de laboratorio de anatomía",
                ),
            }
        ],
    },
    {
        "name": "Guía de Fórmulas de Cálculo Diferencial",
        "slug": "guia-formulas-calculo-diferencial",
        "category_slug": "libros_manuales",
        "thumbnail": "https://images.unsplash.com/photo-1509228468518-180dd4864904?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Guía de Fórmulas de Cálculo Diferencial - Rústica",
                "description": "Guía de fórmulas de cálculo diferencial en pasta rústica, resumen práctico para exámenes.",
                "attribute": "Rústica",
                "variantnumber": 1,
                "slug": "guia-formulas-calculo-diferencial-rustica",
                "sku": "LIB-CALC-001",
                "selling_price": "450.00",
                "tax_rate": "0.00",
                "minimum_stock": 5,
                "initial_stock": 25,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1509228468518-180dd4864904",
                        "https://images.unsplash.com/photo-1509266272358-7701da638078",
                        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b",
                    ],
                    "Guía de fórmulas de cálculo diferencial",
                ),
            }
        ],
    },
    {
        "name": "Estetoscopio Doble Campana",
        "slug": "estetoscopio-doble-campana",
        "category_slug": "laboratorio_medicina",
        "thumbnail": "https://images.unsplash.com/photo-1584362917165-526a968579e8?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Estetoscopio Doble Campana - Negro",
                "description": "Estetoscopio de doble campana en color negro, alta sensibilidad acústica para uso clínico y de laboratorio.",
                "attribute": "Negro",
                "variantnumber": 1,
                "slug": "estetoscopio-doble-campana-negro",
                "sku": "MED-ESTE-001",
                "selling_price": "1850.00",
                "tax_rate": "0.18",
                "minimum_stock": 3,
                "initial_stock": 15,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1584362917165-526a968579e8",
                        "https://images.unsplash.com/photo-1579154204601-01588f351e67",
                        "https://images.unsplash.com/photo-1584515933487-779824d29309",
                    ],
                    "Estetoscopio de doble campana negro",
                ),
            }
        ],
    },
    {
        "name": "Bata Médica de Laboratorio",
        "slug": "bata-medica-laboratorio",
        "category_slug": "laboratorio_medicina",
        "thumbnail": "https://images.unsplash.com/photo-1584982751601-97dcc096659c?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Bata Médica de Laboratorio - Talla M",
                "description": "Bata médica de laboratorio en talla M, tela resistente y bolsillos frontales reforzados.",
                "attribute": "Talla M",
                "variantnumber": 1,
                "slug": "bata-medica-laboratorio-m",
                "sku": "MED-BATA-001-M",
                "selling_price": "1200.00",
                "tax_rate": "0.18",
                "minimum_stock": 5,
                "initial_stock": 30,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1584982751601-97dcc096659c",
                        "https://images.unsplash.com/photo-1576091160550-2173dba999ef",
                        "https://images.unsplash.com/photo-1622253692010-333f2da6031d",
                    ],
                    "Bata médica de laboratorio talla M",
                ),
            },
            {
                "name": "Bata Médica de Laboratorio - Talla L",
                "description": "Bata médica de laboratorio en talla L, tela resistente y bolsillos frontales reforzados.",
                "attribute": "Talla L",
                "variantnumber": 2,
                "slug": "bata-medica-laboratorio-l",
                "sku": "MED-BATA-001-L",
                "selling_price": "1200.00",
                "tax_rate": "0.18",
                "minimum_stock": 5,
                "initial_stock": 25,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1584982751601-97dcc096659c",
                        "https://images.unsplash.com/photo-1576091160550-2173dba999ef",
                        "https://images.unsplash.com/photo-1622253692010-333f2da6031d",
                    ],
                    "Bata médica de laboratorio talla L",
                ),
            },
        ],
    },
    {
        "name": "Set de Reglas T y Escalímetro",
        "slug": "set-reglas-t-escalimetro",
        "category_slug": "arquitectura_arte",
        "thumbnail": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Set de Reglas T y Escalímetro - Estándar",
                "description": "Set estándar de reglas T y escalímetro para dibujo técnico y maquetas de arquitectura.",
                "attribute": "Estándar",
                "variantnumber": 1,
                "slug": "set-reglas-t-escalimetro-estandar",
                "sku": "ARQ-REGLA-001",
                "selling_price": "680.00",
                "tax_rate": "0.18",
                "minimum_stock": 5,
                "initial_stock": 20,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1503387762-592deb58ef4e",
                        "https://images.unsplash.com/photo-1513364776144-60967b0f800f",
                        "https://images.unsplash.com/photo-1503387837-b154d5074bd2",
                    ],
                    "Set de reglas T y escalímetro",
                ),
            }
        ],
    },
    {
        "name": "Calculadora Científica",
        "slug": "calculadora-cientifica",
        "category_slug": "electronicos",
        "thumbnail": "https://images.unsplash.com/photo-1587145820266-a5951ee6f620?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Calculadora Científica - 240 Funciones",
                "description": "Calculadora científica con 240 funciones, pantalla de doble línea, ideal para cursos de ingeniería.",
                "attribute": "240 Funciones",
                "variantnumber": 1,
                "slug": "calculadora-cientifica-240-funciones",
                "sku": "ELE-CALC-001",
                "selling_price": "1450.00",
                "tax_rate": "0.18",
                "minimum_stock": 8,
                "initial_stock": 35,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1587145820266-a5951ee6f620",
                        "https://images.unsplash.com/photo-1587614382346-4ec70e388b28",
                        "https://images.unsplash.com/photo-1554224155-6726b3ff858f",
                    ],
                    "Calculadora científica de 240 funciones",
                ),
            }
        ],
    },
    {
        "name": "Memoria USB",
        "slug": "memoria-usb",
        "category_slug": "electronicos",
        "thumbnail": "https://images.unsplash.com/photo-1618410320928-25228d811631?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "Memoria USB - 32GB Metálica",
                "description": "Memoria USB de 32GB con carcasa metálica resistente, compatible con USB 3.0.",
                "attribute": "32GB",
                "variantnumber": 1,
                "slug": "memoria-usb-32gb-metalica",
                "sku": "ELE-USB-001-32",
                "selling_price": "480.00",
                "tax_rate": "0.18",
                "minimum_stock": 10,
                "initial_stock": 40,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1618410320928-25228d811631",
                        "https://images.unsplash.com/photo-1573164713988-8665fc963095",
                        "https://images.unsplash.com/photo-1541029071515-84cc54f84dc5",
                    ],
                    "Memoria USB de 32GB metálica",
                ),
            },
            {
                "name": "Memoria USB - 64GB Metálica",
                "description": "Memoria USB de 64GB con carcasa metálica resistente, compatible con USB 3.0.",
                "attribute": "64GB",
                "variantnumber": 2,
                "slug": "memoria-usb-64gb-metalica",
                "sku": "ELE-USB-001-64",
                "selling_price": "650.00",
                "tax_rate": "0.18",
                "minimum_stock": 10,
                "initial_stock": 30,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1618410320928-25228d811631",
                        "https://images.unsplash.com/photo-1573164713988-8665fc963095",
                        "https://images.unsplash.com/photo-1541029071515-84cc54f84dc5",
                    ],
                    "Memoria USB de 64GB metálica",
                ),
            },
        ],
    },
    {
        "name": "T-Shirt Institucional UASD",
        "slug": "tshirt-institucional-uasd",
        "category_slug": "uniformes",
        "thumbnail": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&h=400&fit=crop",
        "variants": [
            {
                "name": "T-Shirt Institucional UASD - Talla M",
                "description": "T-Shirt institucional UASD talla M, algodón suave con el logo bordado del Económato.",
                "attribute": "Talla M",
                "variantnumber": 1,
                "slug": "tshirt-institucional-uasd-m",
                "sku": "UNI-TSHIRT-001-M",
                "selling_price": "550.00",
                "tax_rate": "0.18",
                "minimum_stock": 10,
                "initial_stock": 30,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab",
                        "https://images.unsplash.com/photo-1503341504253-dff4815485f1",
                        "https://images.unsplash.com/photo-1576566588028-4147f3842f27",
                    ],
                    "T-Shirt institucional UASD talla M",
                ),
            },
            {
                "name": "T-Shirt Institucional UASD - Talla L",
                "description": "T-Shirt institucional UASD talla L, algodón suave con el logo bordado del Económato.",
                "attribute": "Talla L",
                "variantnumber": 2,
                "slug": "tshirt-institucional-uasd-l",
                "sku": "UNI-TSHIRT-001-L",
                "selling_price": "550.00",
                "tax_rate": "0.18",
                "minimum_stock": 10,
                "initial_stock": 25,
                "images": _gallery(
                    [
                        "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab",
                        "https://images.unsplash.com/photo-1503341504253-dff4815485f1",
                        "https://images.unsplash.com/photo-1576566588028-4147f3842f27",
                    ],
                    "T-Shirt institucional UASD talla L",
                ),
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed an admin employee account and demo products with variants and images"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("\n=== Seeding Admin Employee ==="))
        self._seed_admin_employee()
        self.stdout.write(self.style.SUCCESS("\n✓ Done seeding admin employee.\n"))

        self.stdout.write(self.style.WARNING("=== Seeding Demo Products ==="))
        self._seed_products()
        self.stdout.write(self.style.SUCCESS("\n✓ Done seeding demo products.\n"))

    def _seed_admin_employee(self):
        user, created = User.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={
                "first_name": ADMIN_FIRST_NAME,
                "last_name": ADMIN_LAST_NAME,
                "role": "employee",
                "status": "active",
                "is_staff": True,
                "is_superuser": True,
                "is_email_verified": True,
                "institution_member": True,
            },
        )
        if created:
            user.set_password(ADMIN_PASSWORD)
            user.save()
            self.stdout.write(f"  {user.email} — created")
        else:
            changed = False
            for field, value in {
                "role": "employee",
                "status": "active",
                "is_staff": True,
                "is_superuser": True,
            }.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if changed:
                user.save()
            self.stdout.write(f"  {user.email} — already exists")

        # The "Superuser" profile is the one seeded in accounts/migrations/0006_seed_profiles.py.
        # Keep its permissions in sync with the full current catalog so this profile always
        # grants every employee permission, not just the ones that existed when it was seeded.
        profile, profile_created = Profile.objects.get_or_create(
            name="Superuser",
            defaults={
                "description": "Full access to every employee permission.",
                "permissions": PERMISSION_CODES,
                "is_protected": True,
            },
        )
        if not profile_created and set(profile.permissions) != set(PERMISSION_CODES):
            profile.permissions = PERMISSION_CODES
            profile.save()

        employee, employee_created = employee_model.objects.get_or_create(
            user=user,
            defaults={
                "position": EmployeePosition.ADMIN,
                "profile": profile,
                "is_active": True,
            },
        )
        if not employee_created and (employee.profile_id != profile.id or not employee.is_active):
            employee.profile = profile
            employee.is_active = True
            employee.save()

        status = "created" if employee_created else "already exists"
        self.stdout.write(f"  Employee record ({employee.position}, profile={profile.name}) — {status}")

    def _seed_products(self):
        for product_data in PRODUCTS:
            try:
                category = Category.objects.get(slug=product_data["category_slug"])
            except Category.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Skipping '{product_data['name']}' — category "
                        f"'{product_data['category_slug']}' does not exist."
                    )
                )
                continue

            product, created = Product.objects.get_or_create(
                slug=product_data["slug"],
                defaults={
                    "name": product_data["name"],
                    "category": category,
                    "thumbnail": product_data.get("thumbnail", ""),
                },
            )
            status = "created" if created else "already exists"
            self.stdout.write(f"  {product.name} — {status}")

            for variant_data in product_data["variants"]:
                variant, variant_created = ProductVariant.objects.get_or_create(
                    sku=variant_data["sku"],
                    defaults={
                        "product": product,
                        "name": variant_data["name"],
                        "description": variant_data["description"],
                        "attribute": variant_data.get("attribute", ""),
                        "variantnumber": variant_data["variantnumber"],
                        "slug": variant_data["slug"],
                        "selling_price": Decimal(variant_data["selling_price"]),
                        "tax_rate": Decimal(variant_data.get("tax_rate", "0")),
                        "minimum_stock": variant_data.get("minimum_stock", 0),
                    },
                )

                # Only stock a variant the moment it's created — a variant that
                # already existed may have had its stock adjusted by an admin
                # since, and re-running the seed shouldn't overwrite that.
                if variant_created:
                    create_initial_inventory(variant.id, variant_data.get("initial_stock", 0))
                    self.stdout.write(
                        f"    stocked {variant.name} with {variant_data.get('initial_stock', 0)} units"
                    )

                for image_data in variant_data.get("images", []):
                    ProductImage.objects.get_or_create(
                        product_variant=variant,
                        image=image_data["image"],
                        defaults={
                            "image_type": image_data.get("image_type", ProductImage.ImageType.HERO),
                            "alt_text": image_data.get("alt_text", ""),
                            "order": image_data.get("order", 0),
                        },
                    )
