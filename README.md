# Económato UASD — Backend

API de Django/DRF que impulsa la tienda en línea del Económato de la
Universidad Autónoma de Santo Domingo (UASD): los estudiantes exploran el
catálogo, compran en línea y retiran su pedido en persona en el Económato.
Incluye un panel de administración completo para que el personal gestione
catálogo, inventario, pedidos, usuarios y reportes.

El frontend es una aplicación en Next.js que consume esta API exclusivamente
bajo `/api/v1/`.

---

## Stack técnico

- **Django 6** + **Django REST Framework**, con documentación interactiva
  de la API vía `drf-spectacular` (`/api/schema/`).
- `django-taggit`, `django-cors-headers`, `psycopg2-binary`.
- Python ≥ 3.12, gestionado con `uv` (`pyproject.toml` + `uv.lock`).
- Subida de imágenes de productos a Supabase Storage a través del paquete
  `mediaupload`.

## Instalación y ejecución local

```bash
uv sync
cp .env.example .env   # completar credenciales de DB, email, PayPal, etc.
uv run python manage.py migrate
uv run python manage.py runserver
```

La documentación interactiva de la API queda disponible en `/api/schema/`.

## Arquitectura del proyecto

El sistema está organizado en apps de Django por dominio, todas enrutadas
desde un único punto de entrada (`api/urls.py`):

- `api/` — hub de ruteo y endpoints de sistema.
- `accounts/` — usuarios, autenticación, perfiles, empleados.
- `products/default/` — catálogo: productos, variantes, categorías, imágenes.
- `cart/` — carrito de compras.
- `checkout/` — flujo de checkout y horarios de retiro.
- `payment/` — pago en línea vía PayPal.
- `orders/` — pedidos, ítems y pagos asociados.
- `inventory/` — control de stock basado en movimientos, con trazabilidad
  completa de cada entrada y salida.
- `notifications/` — envío de correos (verificación, recuperación de
  contraseña, alertas de bajo stock).
- `reports/` — reportes administrativos y registro de actividad del sistema.
- `store/` — contenido del portal público (carrusel de la home, etc.).
- `seed/` — datos de demostración.

## Funcionalidades

### Panel de administración (empleados)
- Gestión completa de catálogo: productos, variantes, categorías,
  importación masiva por CSV.
- Gestión de usuarios: listado, detalle, bloqueo/activación, creación de
  empleados y perfiles.
- Gestión de inventario en tiempo real: stock por producto, alertas de bajo
  stock y agotados, resumen general, actualización masiva, historial
  completo de movimientos (recepción, venta, ajuste).
- Gestión de pedidos: listado y detalle de todas las órdenes de clientes.
- Dashboard ejecutivo con resumen general y reportes exportables (órdenes,
  inventario, empleados, clientes, actividad del sistema).

### Tienda en línea (clientes)
- Registro, inicio/cierre de sesión, verificación de correo y recuperación
  de contraseña.
- Catálogo navegable por categoría, con vista de grid o lista.
- Carrito de compras y checkout guiado.
- Selección de horario de retiro entre los próximos 7 días hábiles, con
  franjas disponibles cada hora de 8:00 a.m. a 5:00 p.m.
- Pago en línea seguro con PayPal, integrado directamente en el flujo de
  checkout.
- Historial de pedidos propios y comprobante (voucher) de compra descargable.

### API REST
- Autenticación por sesión de Django con protección CSRF.
- Endpoints administrativos protegidos por rol de empleado; catálogo de
  lectura pública para cualquier visitante.

## Modelo de dominio

- **Productos**: `Product` → `ProductVariant` → `ProductImage`, con
  categorías propias del Económato (papelería, libros/manuales, médico/
  laboratorio, arquitectura/artes, electrónica, uniformes, snacks/bebidas).
- **Inventario basado en ledger**: cada cambio de stock queda registrado
  como un movimiento auditable (`StockMovement`) con balance acumulado —
  el stock actual de una variante siempre refleja su historial completo.
- **Pedidos**: `Order` → `OrderItem` → `OrderPayment`, con estados
  `pending` / `fulfilled` / `returned`.
- **Precios en formato decimal**, evitando los errores de precisión típicos
  de los tipos de punto flotante en operaciones monetarias.

## Despliegue

- **Docker**: `Dockerfile` construye la imagen con `uv sync` y levanta
  `gunicorn` sobre `config.wsgi`, listo para cualquier proveedor de
  contenedores.
- **Vercel**: `vercel.json` permite un despliegue directo, ejecutando
  `uv sync` y las migraciones en el build.
