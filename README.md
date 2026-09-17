# Simple E-commerce Store

A beginner-friendly Django foundation for a simple online store. The project is currently in development and this repository contains Step 5: user registration with Django authentication.

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

## Development Status

Step 5 - User registration completed. Product database, Django Admin, product listing, product details, and registration are available. Login remains planned for a later step.
