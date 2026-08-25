import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import PERMISSION_CODES, EmployeePosition, Profile, User, employee_model
from inventory.inventory import create_initial_inventory
from products.default.models import Category, Product, ProductImage, ProductVariant

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "blue"
ADMIN_FIRST_NAME = "Admin"
ADMIN_LAST_NAME = "Admin"

# Seeded products should read as having been added ~2 weeks ago rather than
# at the exact moment the command runs, so demo data (dashboards, "recently
# added" sorts, etc.) doesn't all cluster at "today". Jittered by a few
# hours per product/variant so they don't all share one identical timestamp.
PRODUCT_SEEDED_DAYS_AGO = 14


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
        "name": "Archivador Carta",
        "slug": "archivador-carta",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61Q+XjLy+LL._AC_SL1422_.jpg",
        "variants": [
            {
                "name": "Archivador Carta - 4 Pulgadas",
                "description": "Archivador resistente tamaño carta",
                "attribute": "4 Pulgadas",
                "variantnumber": 1,
                "slug": "archivador-4-pulgadas",
                "sku": "ARC-4P-001",
                "selling_price": "500",
                "tax_rate": "0.05",
                "minimum_stock": 20,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61Q+XjLy+LL._AC_SL1422_.jpg", "image_type": "HERO", "alt_text": "imagen 1", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/31HWNFuT5KL._AC_.jpg", "image_type": "GALLERY", "alt_text": "imagen 2", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/31HWNFuT5KL._AC_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen del thumbnail", "order": 4},
                ],
            },
            {
                "name": "Archivador Carta - 8 Pulgadas",
                "description": "Archivador resistente tamaño carta",
                "attribute": "8 Pulgadas",
                "variantnumber": 2,
                "slug": "archivador-8-pulgadas",
                "sku": "ARC-8P-001",
                "selling_price": "700",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/31HWNFuT5KL._AC_.jpg", "image_type": "HERO", "alt_text": "imagen de un Archivador Carta - 8 Pulgadas", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/41oLnK54GML._AC_SL1000_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Archivador Carta - 8 Pulgadas", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/31HWNFuT5KL._AC_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Archivador Carta - 8 Pulgadas", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/31HWNFuT5KL._AC_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Archivador Carta - 8 Pulgadas", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61Q+XjLy+LL._AC_SL1422_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Archivador Carta - 8 Pulgadas", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Cuaderno-apollo",
        "slug": "cuaderno-apollo",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61iHCRsGeuL._AC_SL1028_.jpg",
        "variants": [
            {
                "name": "Cuaderno-apollo - Negro",
                "description": "Cuaderno apollo negro",
                "attribute": "Negro",
                "variantnumber": 1,
                "slug": "cuaderno-apollo-negro",
                "sku": "CUADERNO-APOLLO-NEGRO",
                "selling_price": "500",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61iHCRsGeuL._AC_SL1028_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno-apollo - Negro", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/91GSLqcdRCL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno-apollo - Negro", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51AT4e23ZzL._AC_SL1028_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno-apollo - Negro", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51AT4e23ZzL._AC_SL1028_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno-apollo - Negro", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61iHCRsGeuL._AC_SL1028_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno-apollo - Negro", "order": 4},
                ],
            },
            {
                "name": "Cuaderno-apollo - Rojo",
                "description": "Cuaderno apollo Rojo",
                "attribute": "Rojo",
                "variantnumber": 2,
                "slug": "cuaderno-apollo-rojo",
                "sku": "CUADERNO-APOLLO-ROJO",
                "selling_price": "200",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71I750-VrZL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno-apollo - Rojo", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/710bJ8t8g1L._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno-apollo - Rojo", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71PqYD0v4KL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno-apollo - Rojo", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71qk4T2crmL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno-apollo - Rojo", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71I750-VrZL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno-apollo - Rojo", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Libro Administración",
        "slug": "libro-administracion",
        "category_slug": "libros_manuales",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61iNVOIx6oL._SL1491_.jpg",
        "variants": [
            {
                "name": "Libro Administración - Introduccion",
                "description": "Manual de administración",
                "attribute": "Introduccion",
                "variantnumber": 1,
                "slug": "administracion-intro",
                "sku": "ADM-INT-001",
                "selling_price": "28",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61iNVOIx6oL._SL1491_.jpg", "image_type": "HERO", "alt_text": "imagen de un Libro Administración - Introduccion", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51UVk3xCmKL.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Libro Administración - Introduccion", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61iNVOIx6oL._SL1491_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Libro Administración - Introduccion", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Agenda Estudiantil",
        "slug": "agenda-estudiantil",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61qlsNDZuAL._SL1293_.jpg",
        "variants": [
            {
                "name": "Agenda Estudiantil - Semestral-2026",
                "description": "Agenda para planificación académica",
                "attribute": "Semestral-2026",
                "variantnumber": 1,
                "slug": "agenda-semestral",
                "sku": "AGENDA-SEM-001",
                "selling_price": "6.99",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61qlsNDZuAL._SL1293_.jpg", "image_type": "HERO", "alt_text": "imagen de un Agenda Estudiantil - Semestral-2026", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61qlsNDZuAL._SL1293_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Agenda Estudiantil - Semestral-2026", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Bata Estudiante Medicina",
        "slug": "bata-estudiante-medicina",
        "category_slug": "uniformes",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg",
        "variants": [
            {
                "name": "Bata Estudiante Medicina - Talla M",
                "description": "Bata blanca talla mediana",
                "attribute": "Talla M",
                "variantnumber": 1,
                "slug": "bata-med-m",
                "sku": "BAT-MED-M",
                "selling_price": "18",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "HERO", "alt_text": "imagen de un Bata Estudiante Medicina - Talla M", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71UVABfkQWL._AC_SX679_.jpg", "image_type": "GALLERY", "alt_text": "imagen de una Bata Estudiante Medicina - Talla M", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71FJc2FdlPL._AC_SX679_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Bata Estudiante Medicina - Talla M", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71jdGY46eNL._AC_SX679_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Bata Estudiante Medicina - Talla M", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Bata Estudiante Medicina - Talla M", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Bata Médica Manga Larga",
        "slug": "bata-medica-manga-larga",
        "category_slug": "uniformes",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg",
        "variants": [
            {
                "name": "Bata Médica Manga Larga - Talla S",
                "description": "Bata médica blanca talla pequeña",
                "attribute": "Talla S",
                "variantnumber": 1,
                "slug": "bata-medica-s",
                "sku": "BAT-MED-S",
                "selling_price": "28",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "HERO", "alt_text": "imagen de un Bata Médica Manga Larga - Talla S", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71UVABfkQWL._AC_SX679_.jpg", "image_type": "GALLERY", "alt_text": "imagen de una Bata Médica Manga Larga - Talla S", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71FJc2FdlPL._AC_SX679_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Bata Médica Manga Larga - Talla S", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71jdGY46eNL._AC_SX679_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Bata Médica Manga Larga - Talla S", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Bata Médica Manga Larga - Talla S", "order": 4},
                ],
            },
            {
                "name": "Bata Médica Manga Larga - Talla XL",
                "description": "Bata médica blanca talla extra grande",
                "attribute": "Talla XL",
                "variantnumber": 2,
                "slug": "bata-medica-xl",
                "sku": "BAT-MED-XL",
                "selling_price": "32",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "HERO", "alt_text": "imagen de un Bata Médica Manga Larga - Talla XL", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71UVABfkQWL._AC_SX679_.jpg", "image_type": "GALLERY", "alt_text": "imagen de una Bata Médica Manga Larga - Talla XL", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71FJc2FdlPL._AC_SX679_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Bata Médica Manga Larga - Talla XL", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71jdGY46eNL._AC_SX679_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Bata Médica Manga Larga - Talla XL", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Bata Médica Manga Larga - Talla XL", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Bata Blanca Laboratorio",
        "slug": "bata-blanca-laboratorio",
        "category_slug": "uniformes",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg",
        "variants": [
            {
                "name": "Bata Blanca Laboratorio - Talla L",
                "description": "Bata blanca para prácticas de laboratorio talla grande",
                "attribute": "Talla L",
                "variantnumber": 1,
                "slug": "bata-blanca-l",
                "sku": "BATA-L-BLC",
                "selling_price": "27",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "HERO", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla L", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71UVABfkQWL._AC_SX679_.jpg", "image_type": "GALLERY", "alt_text": "imagen de una Bata Blanca Laboratorio - Talla L", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71FJc2FdlPL._AC_SX679_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla L", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71jdGY46eNL._AC_SX679_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla L", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla L", "order": 4},
                ],
            },
            {
                "name": "Bata Blanca Laboratorio - Talla M",
                "description": "Bata blanca para prácticas de laboratorio talla mediana",
                "attribute": "Talla M",
                "variantnumber": 2,
                "slug": "bata-blanca-m",
                "sku": "BATA-M-BLC",
                "selling_price": "25",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "HERO", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla M", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71UVABfkQWL._AC_SX679_.jpg", "image_type": "GALLERY", "alt_text": "imagen de una Bata Blanca Laboratorio - Talla M", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71FJc2FdlPL._AC_SX679_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla M", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71jdGY46eNL._AC_SX679_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla M", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61c31owVEtL._AC_SX679_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Bata Blanca Laboratorio - Talla M", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Agenda Universitaria",
        "slug": "agenda-universitaria",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61qlsNDZuAL._SL1293_.jpg",
        "variants": [
            {
                "name": "Agenda Universitaria - Basica",
                "description": "Agenda académica universitaria tapa azul",
                "attribute": "Basica",
                "variantnumber": 1,
                "slug": "agenda-univarsitaria-2026-azul",
                "sku": "AGENDA--2026-AZU",
                "selling_price": "12.99",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61qlsNDZuAL._SL1293_.jpg", "image_type": "HERO", "alt_text": "imagen de un Agenda Universitaria - Basica", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61qlsNDZuAL._SL1293_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Agenda Universitaria - Basica", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Manual Anatomía Ilustrada",
        "slug": "manual-anatomia-ilustrada",
        "category_slug": "libros_manuales",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/614MT69urdL._SL1293_.jpg",
        "variants": [
            {
                "name": "Manual Anatomía Ilustrada - con ilustraciones",
                "description": "Manual de anatomía con ilustraciones",
                "attribute": "con ilustraciones",
                "variantnumber": 1,
                "slug": "anatomia-color",
                "sku": "LIBRO-ANA-COLOR-001",
                "selling_price": "85",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/614MT69urdL._SL1293_.jpg", "image_type": "HERO", "alt_text": "imagen de un Manual Anatomía Ilustrada - con ilustraciones", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61efX2DFYeL.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Manual Anatomía Ilustrada - con ilustraciones", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/614MT69urdL._SL1293_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Manual Anatomía Ilustrada - con ilustraciones", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Manual Anatomía Humana",
        "slug": "manual-anatomia-humana",
        "category_slug": "libros_manuales",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/614MT69urdL._SL1293_.jpg",
        "variants": [
            {
                "name": "Manual Anatomía Humana - blanco y negro",
                "description": "Manual académico de anatomía humana",
                "attribute": "blanco y negro",
                "variantnumber": 1,
                "slug": "anatomia-vol1",
                "sku": "LIBRO-ANA-VOL1",
                "selling_price": "55",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/614MT69urdL._SL1293_.jpg", "image_type": "HERO", "alt_text": "imagen de un Manual Anatomía Humana - blanco y negro", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61efX2DFYeL.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Manual Anatomía Humana - blanco y negro", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/614MT69urdL._SL1293_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Manual Anatomía Humana - blanco y negro", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Cuaderno Universitario",
        "slug": "cuaderno-universitario",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Cuaderno Universitario - rayado",
                "description": "Cuaderno universitario rayado",
                "attribute": "rayado",
                "variantnumber": 1,
                "slug": "cuaderno-100-rayado",
                "sku": "CUA-100-RAY",
                "selling_price": "2.99",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno Universitario - rayado", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/815p2vj6FlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno Universitario - rayado", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81wEbQisOeL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno Universitario - rayado", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/8162XK93BVL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno Universitario - rayado", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno Universitario - rayado", "order": 4},
                ],
            },
            {
                "name": "Cuaderno Universitario - cuadriculado",
                "description": "Cuaderno universitario cuadriculado",
                "attribute": "cuadriculado",
                "variantnumber": 2,
                "slug": "cuaderno-200-cuad",
                "sku": "CUA-200-CUA",
                "selling_price": "5.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno Universitario - cuadriculado", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/815p2vj6FlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno Universitario - cuadriculado", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81wEbQisOeL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno Universitario - cuadriculado", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/8162XK93BVL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno Universitario - cuadriculado", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno Universitario - cuadriculado", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Cuaderno Composición",
        "slug": "cuaderno-composicion",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Cuaderno Composición - universitario",
                "description": "Cuaderno de composición universitario",
                "attribute": "universitario",
                "variantnumber": 1,
                "slug": "cuaderno-composicion-80",
                "sku": "CUA-COM-80",
                "selling_price": "2.25",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno Composición - universitario", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/815p2vj6FlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno Composición - universitario", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81wEbQisOeL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno Composición - universitario", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/8162XK93BVL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno Composición - universitario", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno Composición - universitario", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Cuaderno Espiral Profesional",
        "slug": "cuaderno-espiral-profesional",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Cuaderno Espiral Profesional - tamano A4",
                "description": "Cuaderno espiral profesional tamaño A4",
                "attribute": "tamano A4",
                "variantnumber": 1,
                "slug": "cuaderno-espiral-a4-200",
                "sku": "CUA-ESP-A4-200",
                "selling_price": "7.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno Espiral Profesional - tamano A4", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/815p2vj6FlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno Espiral Profesional - tamano A4", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81wEbQisOeL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno Espiral Profesional - tamano A4", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/8162XK93BVL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno Espiral Profesional - tamano A4", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno Espiral Profesional - tamano A4", "order": 4},
                ],
            },
            {
                "name": "Cuaderno Espiral Profesional - A5 100 Hojas",
                "description": "Cuaderno espiral profesional tamaño A5",
                "attribute": "A5 100 Hojas",
                "variantnumber": 2,
                "slug": "cuaderno-espiral-a5-100",
                "sku": "CUA-ESP-A5-100",
                "selling_price": "4.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno Espiral Profesional - A5 100 Hojas", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/815p2vj6FlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno Espiral Profesional - A5 100 Hojas", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81wEbQisOeL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno Espiral Profesional - A5 100 Hojas", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/8162XK93BVL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno Espiral Profesional - A5 100 Hojas", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno Espiral Profesional - A5 100 Hojas", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Cuaderno Universitario Rayado",
        "slug": "cuaderno-universitario-rayado",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Cuaderno Universitario Rayado - 100 Páginas Azul",
                "description": "Cuaderno universitario rayado color azul con 100 páginas",
                "attribute": "100 Páginas Azul",
                "variantnumber": 1,
                "slug": "cuaderno-100-azul",
                "sku": "CUAD100-AZL-001",
                "selling_price": "3.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno Universitario Rayado - 100 Páginas Azul", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/815p2vj6FlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno Universitario Rayado - 100 Páginas Azul", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81wEbQisOeL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno Universitario Rayado - 100 Páginas Azul", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/8162XK93BVL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno Universitario Rayado - 100 Páginas Azul", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno Universitario Rayado - 100 Páginas Azul", "order": 4},
                ],
            },
            {
                "name": "Cuaderno Universitario Rayado - 200 Páginas Negro",
                "description": "Cuaderno universitario rayado color negro con 200 páginas",
                "attribute": "200 Páginas Negro",
                "variantnumber": 2,
                "slug": "cuaderno-200-negro",
                "sku": "CUAD200-NGR-001",
                "selling_price": "5.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Cuaderno Universitario Rayado - 200 Páginas Negro", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/815p2vj6FlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Cuaderno Universitario Rayado - 200 Páginas Negro", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81wEbQisOeL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cuaderno Universitario Rayado - 200 Páginas Negro", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/8162XK93BVL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Cuaderno Universitario Rayado - 200 Páginas Negro", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71znry+maFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cuaderno Universitario Rayado - 200 Páginas Negro", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Bolígrafo Azul",
        "slug": "boligrafo-azul",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71CezrJzKRL._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Bolígrafo Azul - Bolígrafo Azul",
                "description": "Bolígrafo tinta azul económico paquete de 10 lapiceros",
                "attribute": "Bolígrafo Azul",
                "variantnumber": 1,
                "slug": "boligrafo-azul-unidad",
                "sku": "BOL-AZU-001",
                "selling_price": "0.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71CezrJzKRL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Bolígrafo Azul - Bolígrafo Azul", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61YpCQTCVVL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Bolígrafo Azul - Bolígrafo Azul", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61WMqXMYPlL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Bolígrafo Azul - Bolígrafo Azul", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71B6FbsPwEL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Bolígrafo Azul - Bolígrafo Azul", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71CezrJzKRL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Bolígrafo Azul - Bolígrafo Azul", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Bolígrafo Negro",
        "slug": "boligrafo-negro",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81XO7iqWH0L._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Bolígrafo Negro - Bolígrafo Negro",
                "description": "Bolígrafo tinta negra paquete de 10 lapiceros",
                "attribute": "Bolígrafo Negro",
                "variantnumber": 1,
                "slug": "boligrafo-negro-unidad",
                "sku": "BOL-NGR-001",
                "selling_price": "0.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81XO7iqWH0L._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Bolígrafo Negro - Bolígrafo Negro", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71Ft2NRHvlL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Bolígrafo Negro - Bolígrafo Negro", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61CJpe53epL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Bolígrafo Negro - Bolígrafo Negro", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/718CsP7EZjL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Bolígrafo Negro - Bolígrafo Negro", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81XO7iqWH0L._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Bolígrafo Negro - Bolígrafo Negro", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Calculadora Básica",
        "slug": "calculadora-basica",
        "category_slug": "electronicos",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71MD+gF1tNL._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Calculadora Básica - 12 Dígitos",
                "description": "Calculadora de escritorio 12 dígitos",
                "attribute": "12 Dígitos",
                "variantnumber": 1,
                "slug": "calculadora-12-digitos",
                "sku": "CAL-12DIG-001",
                "selling_price": "10.99",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71MD+gF1tNL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Calculadora Básica - 12 Dígitos", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71JvQIeOMfL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Calculadora Básica - 12 Dígitos", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71tdOsWSsZL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Calculadora Básica - 12 Dígitos", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71RIaUVfOmL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Calculadora Básica - 12 Dígitos", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71MD+gF1tNL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Calculadora Básica - 12 Dígitos", "order": 4},
                ],
            },
            {
                "name": "Calculadora Básica - 8 Dígitos",
                "description": "Calculadora básica de escritorio",
                "attribute": "8 Dígitos",
                "variantnumber": 2,
                "slug": "calculadora-8dig",
                "sku": "CAL-8DIG",
                "selling_price": "8.99",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/711gsV7aL9L._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71emJajrF9L._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71+bagLWD4L._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71d6q6u85gL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/711gsV7aL9L._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 4},
                ],
            },
            {
                "name": "Calculadora Básica - 8 Dígitos",
                "description": "Calculadora básica económica",
                "attribute": "8 Dígitos",
                "variantnumber": 3,
                "slug": "calculadora-8-digitos",
                "sku": "CAL-8DIG-001",
                "selling_price": "7.99",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/611H6KmaCJL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71eHFtpa0YL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71eEk++mAYL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71v2617LRlL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/611H6KmaCJL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Calculadora Básica - 8 Dígitos", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Carpeta Plástica",
        "slug": "carpeta-plastica",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61-OQG+UD3L._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Carpeta Plástica - Color Azul",
                "description": "Carpeta plástica tamaño carta",
                "attribute": "Color Azul",
                "variantnumber": 1,
                "slug": "carpeta-azul",
                "sku": "CAR-AZU-001",
                "selling_price": "2.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61-OQG+UD3L._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Carpeta Plástica - Color Azul", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81XGC8k5JeL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Carpeta Plástica - Color Azul", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71mcK9HOPLL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Carpeta Plástica - Color Azul", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/81cSLOIeCaL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Carpeta Plástica - Color Azul", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61-OQG+UD3L._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Carpeta Plástica - Color Azul", "order": 4},
                ],
            },
        ],
    },
    {
        "name": "Cartulina Blanca",
        "slug": "cartulina-blanca",
        "category_slug": "arquitectura_arte",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/cartulina.jpg",
        "variants": [
            {
                "name": "Cartulina Blanca - Pliego",
                "description": "Cartulina blanca para proyectos académicos",
                "attribute": "Pliego",
                "variantnumber": 1,
                "slug": "cartulina-blanca-pliego",
                "sku": "CAR-BLA-001",
                "selling_price": "0.75",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/cartulina.jpg", "image_type": "HERO", "alt_text": "imagen de un Cartulina Blanca - Pliego", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/cartulina.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cartulina Blanca - Pliego", "order": 4},
                ],
            },
            {
                "name": "Cartulina Blanca - Pliego Individual",
                "description": "Cartulina blanca para proyectos",
                "attribute": "Pliego Individual",
                "variantnumber": 2,
                "slug": "cartulina-blanca",
                "sku": "CAR-BLC-001",
                "selling_price": "0.75",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                ],
            },
        ],
    },
    {
        "name": "Cartulina Colores",
        "slug": "cartulina-colores",
        "category_slug": "arquitectura_arte",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/cartulina.jpg",
        "variants": [
            {
                "name": "Cartulina Colores - Paquete 10 Colores",
                "description": "Cartulinas de colores surtidos",
                "attribute": "Paquete 10 Colores",
                "variantnumber": 1,
                "slug": "cartulina-colores-10",
                "sku": "CAR-COL-10",
                "selling_price": "5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/cartulina.jpg", "image_type": "HERO", "alt_text": "imagen de un Cartulina Blanca - Pliego", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/cartulina.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Cartulina Blanca - Pliego", "order": 4},

                ],
            },
        ],
    },
    {
        "name": "Carpeta Manila",
        "slug": "carpeta-manila",
        "category_slug": "papeleria",
        "thumbnail": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51aFAjf6qFL._AC_SL1500_.jpg",
        "variants": [
            {
                "name": "Carpeta Manila - Carta",
                "description": "Carpeta manila tamaño carta",
                "attribute": "Carta",
                "variantnumber": 1,
                "slug": "carpeta-manila-carta",
                "sku": "CAR-MAN-CAR",
                "selling_price": "0.5",
                "tax_rate": "0.05",
                "minimum_stock": 10,
                "initial_stock": 100,
                "images": [
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51aFAjf6qFL._AC_SL1500_.jpg", "image_type": "HERO", "alt_text": "imagen de un Carpeta Manila - Carta", "order": 0},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61TWj2JKYjL._AC_SL1500_.jpg", "image_type": "GALLERY", "alt_text": "imagen de un Carpeta Manila - Carta", "order": 1},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/61H9A3lHOxL._AC_SL1500_.jpg", "image_type": "DETAIL", "alt_text": "imagen de un Cartulina Blanca - Pliego", "order": 2},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/71Epxy6HGZL._AC_SL1500_.jpg", "image_type": "LIFESTYLE", "alt_text": "imagen de un Carpeta Manila - Carta", "order": 3},
                    {"image": "https://zdnhvnvrngxvxedrvuon.supabase.co/storage/v1/object/public/bucket1/images/51aFAjf6qFL._AC_SL1500_.jpg", "image_type": "THUMBNAIL", "alt_text": "imagen de un Carpeta Manila - Carta", "order": 4},
                ],
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

    def _seeded_timestamp(self):
        return timezone.now() - timedelta(
            days=PRODUCT_SEEDED_DAYS_AGO,
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

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
            if created:
                seeded_at = self._seeded_timestamp()
                Product.objects.filter(pk=product.pk).update(created_at=seeded_at, updated_at=seeded_at)
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
                    seeded_at = self._seeded_timestamp()
                    ProductVariant.objects.filter(pk=variant.pk).update(created_at=seeded_at, updated_at=seeded_at)
                    # Backdate the initial stock movement to match — otherwise
                    # it keeps today's real timestamp and, since it's the
                    # newest movement by date_time, permanently shadows every
                    # later (correctly backdated) sale when "current stock"
                    # is computed from the most recent movement's balance.
                    create_initial_inventory(variant.id, variant_data.get("initial_stock", 0), date_time=seeded_at)
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
