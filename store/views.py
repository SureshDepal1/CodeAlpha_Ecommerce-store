from django.shortcuts import render

from .models import Product


def home(request):
    return render(request, "store/home.html")


def product_list(request):
    products = Product.objects.filter(is_available=True).order_by("-created_at")
    return render(request, "store/product_list.html", {"products": products})
