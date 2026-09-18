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
