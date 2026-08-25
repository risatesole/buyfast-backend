# Económato UASD — Backend

API de Django/DRF para la tienda en línea del **Económato de la UASD** (una
cooperativa universitaria en República Dominicana): los estudiantes navegan
el catálogo, pagan en línea y retiran su pedido en persona en el Económato.

El frontend es una aplicación aparte en Next.js que consume esta API
exclusivamente bajo `/api/v1/` (ver el `CLAUDE.md` del proyecto `frontend`).

---

## Stack técnico

- **Django 6** + **Django REST Framework**, esquema OpenAPI vía
  `drf-spectacular` (`/api/schema/`).
- `django-taggit`, `django-cors-headers`, `whitenoise`, `psycopg2-binary`.
- Python ≥ 3.12, gestionado con `uv` (`pyproject.toml` + `uv.lock`, espejado
  en `requirements.txt` para Docker/Vercel).
- Subida de imágenes de productos vía un paquete local `mediaupload`
  (`packages/mediaupload`) que envuelve el SDK de Supabase Storage.
- Sin Celery, sin Channels — nada asíncrono pese a que existe `asgi.py`.

## Instalación y ejecución local

```bash
uv sync
cp .env.example .env   # completar credenciales de DB, email, PayPal, etc.
uv run python manage.py migrate
uv run python manage.py runserver
```

El esquema/documentación interactiva de la API queda disponible en
`/api/schema/` una vez el servidor está corriendo.

## Arquitectura del proyecto

El sistema está dividido en apps de Django por dominio, todas enrutadas desde
un único punto de entrada:

- `api/` — hub de ruteo: **`api/urls.py` es la única fuente de verdad** para
  todas las URLs del proyecto (cada endpoint se registra ahí, aunque su
  vista viva en otra app).
- `accounts/` — usuarios, autenticación, perfiles, empleados.
- `products/default/` — catálogo (productos, variantes, categorías,
  imágenes). Es la app más arquitecturada (`entities/`, `value_objects/`,
  `repositories/`, `services/`); el resto del proyecto usa un estilo más
  simple basado en funciones `usecases/`.
- `cart/` — carrito de compras.
- `checkout/` — flujo de checkout y horarios de retiro.
- `payment/` — integración con PayPal (sandbox) y validación de tarjeta.
- `orders/` — pedidos y sus ítems/pagos.
- `inventory/` — control de stock basado en movimientos (ledger), no en un
  contador mutable.
- `notifications/` — envío de correos (verificación, recuperación de
  contraseña, etc.).
- `reports/` — reportes administrativos (órdenes, inventario, empleados,
  clientes) y registro de logs.
- `store/` — contenido del portal público (p. ej. el carrusel de la home).
- `seed/` — datos de prueba/semilla.

## Módulos funcionales

### Panel de administración (empleados)
- Gestión de catálogo: productos, variantes, categorías, importación por CSV.
- Gestión de usuarios: listado, detalle, bloqueo/activación, creación de
  empleados, perfiles.
- Gestión de inventario: listado con stock, productos con bajo stock/agotados,
  resumen de inventario, actualización masiva, movimientos de stock
  (recepción, venta, ajuste).
- Gestión de pedidos: listado y detalle de órdenes de todos los clientes.
- Dashboard con resumen general y reportes exportables (órdenes, inventario,
  empleados, clientes, logs del sistema).

### Tienda pública (clientes)
- Registro, inicio/cierre de sesión, verificación de correo, recuperación de
  contraseña, edición de perfil y avatar.
- Catálogo de productos navegable (grid/lista) con categorías.
- Carrito de compras y checkout con selección de horario de retiro.
- Pago con PayPal (sandbox) y validación de tarjeta.
- Historial de pedidos propios y comprobante (voucher) de compra.

### API REST
- Autenticación basada en **sesión de Django** (cookie + CSRF token), no JWT
  — aunque `djangorestframework-simplejwt` está instalado, no está en uso.
- Los endpoints administrativos (`/admin/...`) requieren rol `employee`; los
  de cliente requieren sesión autenticada; el catálogo es de lectura pública.

## Modelo de dominio (resumen)

- **Productos**: `Product` → `ProductVariant` → `ProductImage`. Categorías
  específicas del Económato (papelería, libros/manuales, médico/laboratorio,
  arquitectura/artes, electrónica, uniformes, snacks/bebidas).
- **Inventario basado en ledger**: cada cambio de stock queda registrado como
  un `StockMovement` (`initial_inventory`, `purchase_entry`, `customer_sell`)
  con un balance acumulado; el stock actual de una variante es el balance de
  su último movimiento.
- **Pedidos**: `Order` (estados: `pending` / `fulfilled` / `returned`) →
  `OrderItem` → `OrderPayment`.
- **Pagos**: actualmente solo se valida la tarjeta (Luhn); el flujo de PayPal
  sandbox está implementado, pero el procesamiento genérico de pagos
  (`payment/usecases/process_payment.py`) no está conectado al checkout.
- Los precios se almacenan siempre en tipo `Decimal`, nunca en punto
  flotante (con la excepción histórica de `OrderItem`/`OrderPayment`, que
  todavía usan `FloatField`).

## Estado conocido / limitaciones actuales

- Los horarios de retiro (`checkout/timeslots`) son datos de prueba
  hardcodeados, no un modelo real de agenda.
- No existe una suite de tests para la mayoría de las apps (solo
  `cart/tests/` tiene tests reales).
- Ver `CLAUDE.md` para el detalle completo de deuda técnica conocida y
  convenciones de desarrollo.

## Despliegue

- **Docker**: `Dockerfile` instala dependencias desde `requirements.txt` y
  levanta `gunicorn` sobre `config.wsgi`.
- **Vercel**: `vercel.json` corre `uv sync` + migraciones en el build y sirve
  `config/wsgi.py` como función Python.
