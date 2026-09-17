from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RegistrationForm
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
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully.")
            return redirect("store:home")
    else:
        form = RegistrationForm()

    return render(request, "store/register.html", {"form": form})
