from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


CENT = Decimal("0.01")


def _money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_totals(subtotal):
    subtotal = _money(subtotal)
    shipping_cost = _money(settings.SHIPPING_FLAT_RATE)
    if settings.FREE_SHIPPING_THRESHOLD is not None and subtotal >= settings.FREE_SHIPPING_THRESHOLD:
        shipping_cost = Decimal("0.00")
    tax_amount = _money(subtotal * settings.TAX_RATE_PERCENT / Decimal("100"))
    total = _money(subtotal + shipping_cost + tax_amount)
    return {
        "subtotal": subtotal,
        "shipping_cost": shipping_cost,
        "tax_amount": tax_amount,
        "total": total,
    }
