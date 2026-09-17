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
