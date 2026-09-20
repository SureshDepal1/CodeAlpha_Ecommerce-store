def cart_count(request):
    cart = request.session.get("cart", {})
    total_quantity = 0

    if cart:
        for quantity in cart.values():
            try:
                total_quantity += int(quantity)
            except (TypeError, ValueError):
                continue

    return {"cart_count": total_quantity}


def nav_categories(request):
    categories = (
        request.site.products.filter(is_available=True) if hasattr(request, "site") and hasattr(request.site, "products") else None
    )
    if categories is None:
        categories = __import__("store.models", fromlist=["Product"]).Product.objects.filter(is_available=True)

    ordered = []
    seen = set()
    for value in categories.exclude(category__isnull=True).exclude(category="").values_list("category", flat=True):
        cleaned = (value or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    ordered.sort(key=str.casefold)
    return {"nav_categories": ordered[:12]}
