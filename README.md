# Simple E-commerce Store

A beginner-friendly Django foundation for a simple online store. The project is currently in development and this repository contains Step 7: Basic Shopping Cart using Django sessions.

## Features

Planned features include:

- Product listings
- Product details
- Shopping cart
- User registration/login
- Checkout
- Order processing
- Order history
- Search and filtering

## Technology

- Python
- Django
- HTML
- CSS
- JavaScript
- SQLite

## Installation

### 1. Clone the repository

```powershell
git clone <repository-url>
cd simple-ecommerce-store
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
```

### 3. Activate the virtual environment

Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
venv\Scripts\activate
```

### 4. Install requirements

```powershell
pip install -r requirements.txt
```

For development-only image downloads, install the optional tools too:

```powershell
pip install -r requirements-dev.txt
```

To regenerate the requirements file after installing packages:

```powershell
pip freeze > requirements.txt
```

### 5. Run migrations

```powershell
python manage.py migrate
```

### 6. Start the development server

```powershell
python manage.py runserver
```

Open the homepage at http://127.0.0.1:8000/.

The Django admin is available at http://127.0.0.1:8000/admin/. Create an administrator account when needed with:

```powershell
python manage.py createsuperuser
```

## Step 2 - Product Database

The Product model has been created with fields for product details, pricing, stock, availability, categories, timestamps, and optional images. Products can be created and managed through Django Admin.

SQLite is currently being used for development. Product images use Django's local media configuration and are stored under the `media/` directory when uploaded. Uploaded media is excluded from version control.

To test the Product model, run:

```powershell
python manage.py test
```

## Step 3 - Product Listing Page

Products are retrieved from the database and only available products are displayed at `/products/`. Product cards include product details, optional uploaded images, stock status, and a placeholder View Details button. A responsive product grid and automated listing tests have been added.

## Step 4 - Product Details Page

Available products can now be viewed individually at `/products/<product_id>/`. Product details are loaded from the database, while nonexistent or unavailable products return a standard 404 response. A responsive product detail layout and automated detail-page tests have been added.

## Step 5 - User Registration

Django's built-in authentication system now supports user registration at `/register/`. The form collects username, email, password, and password confirmation. Django handles secure password hashing, while built-in validation and automated registration tests protect the flow. Login will be implemented in a later step.

## Step 6 - User Login and Logout

Django's built-in authentication system now supports login at `/login/` and logout at `/logout/`. Django sessions manage authentication state, and built-in form validation and authentication tests cover valid and invalid login attempts. Shopping cart and other future features remain planned.

## Step 7 - Basic Shopping Cart

The cart uses Django sessions to store product IDs and quantities, while the Product table remains the source of truth for pricing, availability, stock, and images. Authenticated users can add available products to the cart, the cart page shows each item's quantity, subtotal, and the total, and the navigation displays the live total item count. Stock validation prevents quantities from exceeding available inventory, and checkout remains planned for a future step.

## Step 8 - Cart Management

Authenticated users can now increase, decrease, update, and remove products from their Django session cart. Quantity updates respect product stock limits, the cart total is recalculated from current database prices, and the cart count stays synchronized with the live session data. Checkout and order processing remain planned for later steps.

## Development Status

Step 8 - Cart management completed. Product database, Django Admin, product listing, product details, registration, login, logout, and session-based cart management are available.

## Step 10 - Order Processing

Checkout now creates atomic `Order` and `OrderItem` records from the authenticated user's session cart. Prices and product names are saved as historical snapshots, stock is locked and reduced safely, and the cart is cleared only after a successful order. Customers are redirected to an owner-protected order confirmation page, and administrators can manage orders and their items through Django Admin. Automated tests cover validation, totals, stock, snapshots, security, transactions, and checkout regressions.

## Step 11 - User Order History

Authenticated customers can view their own orders at `/orders/`, open complete order details, and return to shopping. History and detail views enforce server-side order ownership, display stored historical item snapshots, and handle deleted products without breaking old orders. Responsive templates and automated history, security, navigation, and historical-data tests are included.

## Step 12 - Product Search and Filtering

The products page now supports GET-based search across product names, descriptions, and categories, dynamic category filtering, availability filtering, Decimal-safe price ranges, and fixed-option sorting. Filters can be combined, preserve their values in the responsive filter UI, show result counts, and provide clear empty states and a Clear Filters link. Automated tests cover search, categories, prices, availability, sorting, combined filters, and existing feature regressions.

## Step 13 - Security and Error Handling

Security-sensitive settings are configurable through `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_SECURE_DEPLOYMENT`. Local development remains available over HTTP, while production can enable secure cookies, HTTPS redirect, HSTS, content-type protection, same-origin referrer policy, and clickjacking protection. Authentication, CSRF, cart quantities, server-side order totals, ownership checks, filter input, and expected errors are covered by security-focused tests. Custom 404 and 500 pages avoid exposing technical details. For production, set `DJANGO_DEBUG=False`, provide a strong `DJANGO_SECRET_KEY`, configure `DJANGO_ALLOWED_HOSTS`, and set `DJANGO_SECURE_DEPLOYMENT=True` behind HTTPS.

## Email verification

New registrations start inactive and receive a six-digit email code at `/verify/`. The code is valid for 10 minutes, can be resent with a server-enforced cooldown and limit, and is stored only as a user-specific HMAC. Existing accounts without a verification record remain trusted and can log in normally. The OTP settings can be overridden with `OTP_*`, `UNVERIFIED_ACCOUNT_LIFETIME_MINUTES`, `OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR`, and `OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR` environment values or Django test overrides.

Expired inactive registrations can be removed safely with:

```powershell
venv\Scripts\python.exe manage.py purge_unverified_users
```

With the development console email backend, the verification code is printed in the terminal running `runserver`. Configure the SMTP values in `.env` before using a real inbox.

## Deploying

Set these variables in the hosting provider's secret/environment settings. Do not commit `.env` or real credentials.

| Variable | Production value |
| --- | --- |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | A generated key of at least 50 characters |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated public hostnames |
| `DJANGO_SECURE_DEPLOYMENT` | `True` when HTTPS security headers are wanted |
| `DJANGO_BEHIND_PROXY` | `True` only when a trusted TLS proxy sets `X-Forwarded-Proto` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated `https://` origins |
| `DJANGO_SSL_REDIRECT` | Usually `True`; set `False` when the proxy handles redirects |
| `SERVE_MEDIA` | `True` only for a small store on a persistent disk |
| `DATABASE_URL` | Optional `postgresql://...`; SQLite remains the default |
| `DJANGO_CACHE_BACKEND` | `locmem` by default; use `database` for multiple processes |
| `SITE_URL` | The public `https://` URL |
| `EMAIL_*` | Real SMTP host, user, app password, port, and TLS/SSL settings |
| `ORDER_NOTIFICATION_EMAILS` | Comma-separated owner addresses |

First deployment:

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py check --deploy
```

SQLite and local media require a persistent disk on the host. `SERVE_MEDIA=True` is suitable for a small store with persistent storage; object storage or nginx is better at scale. PostgreSQL is supported through `DATABASE_URL` for hosts with ephemeral disks.

For a multi-process deployment using the database cache, set `DJANGO_CACHE_BACKEND=database` and run `python manage.py createcachetable` once.

If secrets were ever shared, rotate the Gmail App Password immediately. Git history keeps old commits, so make the repository private and consider removing exposed history through your repository provider's documented secret-removal process.
