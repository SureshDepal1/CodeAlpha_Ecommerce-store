# Simple E-commerce Store

A beginner-friendly Django foundation for a simple online store. The project is currently in development and this repository contains Step 1: the project setup and homepage foundation.

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

## Development Status

Step 1 - Project setup completed.
