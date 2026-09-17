from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegistrationForm
from .models import Product


def home(request):
    return render(request, "store/home.html")


def product_list(request):
    products = Product.objects.filter(is_available=True).order_by("-created_at")
    return render(request, "store/product_list.html", {"products": products})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_available=True)
    return render(request, "store/product_detail.html", {"product": product})


@login_required(login_url="store:login")
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if not product.is_available:
        messages.error(request, "Product is unavailable.")
        return redirect("store:cart")

    if product.stock <= 0:
        messages.error(request, "Product is out of stock.")
        return redirect("store:cart")

    cart = request.session.get("cart", {})
    current_quantity = int(cart.get(str(product.id), 0))
    next_quantity = current_quantity + 1

    if next_quantity > product.stock:
        messages.error(request, "Maximum available stock has been reached.")
        return redirect("store:cart")

    cart[str(product.id)] = next_quantity
    request.session["cart"] = cart
    request.session.modified = True
    messages.success(request, "Product added to cart.")
    return redirect("store:cart")


@login_required(login_url="store:login")
def cart_view(request):
    cart = request.session.get("cart", {})
    cart_items = []
    total = Decimal("0.00")

    if cart:
        for product_id, quantity in cart.items():
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                continue

            if quantity <= 0:
                continue

            product = Product.objects.filter(pk=product_id).first()
            if product is None or not product.is_available or product.stock <= 0:
                continue

            item_quantity = min(quantity, product.stock)
            if item_quantity != quantity:
                cart[str(product.id)] = item_quantity
                request.session.modified = True

            subtotal = product.price * item_quantity
            cart_items.append(
                {
                    "product": product,
                    "quantity": item_quantity,
                    "subtotal": subtotal,
                }
            )
            total += subtotal

    if cart:
        cleaned_cart = {}
        for product_id, quantity in cart.items():
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                continue
            if quantity > 0:
                cleaned_cart[str(product_id)] = quantity
        request.session["cart"] = cleaned_cart
        request.session.modified = True

    if not cart_items:
        request.session["cart"] = {}
        request.session.modified = True

    return render(
        request,
        "store/cart.html",
        {"cart_items": cart_items, "total": total, "cart_count": sum(item["quantity"] for item in cart_items)},
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("store:home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully.")
            return redirect("store:home")
    else:
        form = RegistrationForm()

    return render(request, "store/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("store:home")

    if request.method == "POST":
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("store:home")
    else:
        form = LoginForm(request=request)

    return render(request, "store/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("store:home")
