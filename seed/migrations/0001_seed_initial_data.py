from django.db import migrations


PROVIDERS = [
    {"name": "Los Santos Bank",               "description": "Los Santos Bank payment provider"},
    {"name": "Banco Popular Dominicana",       "description": "Banco Popular Dominicana payment provider"},
    {"name": "Banreservas",                    "description": "Banco de Reservas de la Republica Dominicana"},
]

DEFAULT_PROVIDER_NAME = "Banreservas"

CATEGORIES = [
    {
        "slug": "papeleria",
        "name": "Papelería y Suministros",
        "description": "Cuadernos, bolígrafos, papel y material gastable.",
        "priority": 1,
        "image_banner": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=400&fit=crop",
        "image_cart": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=100&h=100&fit=crop",
        "image_default": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=400&h=400&fit=crop",
    },
    {
        "slug": "libros_manuales",
        "name": "Libros y Manuales",
        "description": "Textos universitarios, manuales de laboratorio y guías.",
        "priority": 1,
        "image_banner": "https://images.unsplash.com/photo-150784272343-583f20270319?w=1200&h=400&fit=crop",
        "image_cart": "https://images.unsplash.com/photo-1507842872343-583f20270319?w=100&h=100&fit=crop",
        "image_default": "https://images.unsplash.com/photo-1507842872343-583f20270319?w=400&h=400&fit=crop",
    },
    {
        "slug": "laboratorio_medicina",
        "name": "Medicina y Laboratorio",
        "description": "Estetoscopios, batas médicas, kits de disección y bioseguridad.",
        "priority": 1,
        "image_banner": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=1200&h=400&fit=crop",
        "image_cart": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=100&h=100&fit=crop",
        "image_default": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=400&h=400&fit=crop",
    },
    {
        "slug": "arquitectura_arte",
        "name": "Arquitectura y Artes",
        "description": "Reglas T, escalímetros, maquetas, pinturas y pinceles.",
        "priority": 2,
        "image_banner": "https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=1200&h=400&fit=crop",
        "image_cart": "https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=100&h=100&fit=crop",
        "image_default": "https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=400&h=400&fit=crop",
    },
    {
        "slug": "electronicos",
        "name": "Electrónica y Calculadoras",
        "description": "Calculadoras científicas, memorias USB y accesorios periféricos.",
        "priority": 2,
        "image_banner": "https://images.unsplash.com/photo-1550355291-bbee04a92027?w=1200&h=400&fit=crop",
        "image_cart": "https://images.unsplash.com/photo-1550355291-bbee04a92027?w=100&h=100&fit=crop",
        "image_default": "https://images.unsplash.com/photo-1550355291-bbee04a92027?w=400&h=400&fit=crop",
    },
    {
        "slug": "uniformes",
        "name": "Uniformes e Institucional",
        "description": "T-shirts UASD, ropa deportiva y promocionales.",
        "priority": 3,
        "image_banner": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1200&h=400&fit=crop",
        "image_cart": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=100&h=100&fit=crop",
        "image_default": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=400&fit=crop",
    },
    {
        "slug": "material_escolar",
        "name": "Materiales Escolares",
        "description": "Materiales escolares",
        "priority": 3,
        "image_banner": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51UXrrCNLOL._AC_SL1500_.jpg",
        "image_cart": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51UXrrCNLOL._AC_SL1500_.jpg",
        "image_default": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51UXrrCNLOL._AC_SL1500_.jpg",
    },
]

SLIDES = [
    {
        "id": "1",
        "image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/carrousel/calculadoras.png",
        "title": "Calculadoras",
        "description": "Descubre la que va con tu estilo",
        "button_text": "Comprar Ahora",
        "button_link": "categories",
        "order": 1,
        "is_active": True,
    },
    {
        "id": "2",
        "image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/carrousel/manualeslab.png",
        "title": "Ya Disponibles",
        "description": "No pierdas tiempo ahora es más rápido",
        "button_text": "Ver Todos",
        "button_link": "categories",
        "order": 2,
        "is_active": True,
    },
    {
        "id": "3",
        "image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/carrousel/econodigital.jpeg",
        "title": "BuyFast",
        "description": "El mismo ecónomato, pero digital",
        "button_text": "Ver todas las categorias",
        "button_link": "categories",
        "order": 3,
        "is_active": True,
    },
]


def seed_initial_data(apps, schema_editor):
    PaymentProvider = apps.get_model("payment", "PaymentProvider")
    Category = apps.get_model("products", "Category")
    CarouselSlide = apps.get_model("store", "CarouselSlide")

    for data in PROVIDERS:
        provider, _ = PaymentProvider.objects.get_or_create(
            name=data["name"],
            defaults={"description": data["description"]},
        )

        is_default = provider.name == DEFAULT_PROVIDER_NAME
        if provider.is_default != is_default:
            provider.is_default = is_default
            provider.save()

    for data in CATEGORIES:
        Category.objects.get_or_create(
            slug=data["slug"],
            defaults={
                "name": data["name"],
                "description": data["description"],
                "priority": data["priority"],
                "image_banner": data["image_banner"],
                "image_cart": data["image_cart"],
                "image_default": data["image_default"],
            },
        )

    for slide_data in SLIDES:
        CarouselSlide.objects.update_or_create(
            id=slide_data["id"],
            defaults=slide_data,
        )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("payment", "0003_paymentprovider_is_default"),
        ("products", "0013_productvariant_low_stock_notified_and_more"),
        ("store", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_initial_data, reverse_code=migrations.RunPython.noop),
    ]
