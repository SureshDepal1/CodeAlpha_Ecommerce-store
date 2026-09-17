from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404, redirect, render

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
