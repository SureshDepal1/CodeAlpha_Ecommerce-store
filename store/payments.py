from .models import Order


PAYMENT_METHOD_CHOICES = (
    (Order.PaymentMethod.COD, "Cash on Delivery"),
)


PAYMENT_METHOD_REGISTRY = {
    Order.PaymentMethod.COD: {
        "label": "Cash on Delivery",
        "description": "Pay the store when your order is delivered.",
        "available": True,
    },
}


# Add a gateway adapter here when merchant credentials and a provider are available.
def available_payment_methods():
    return tuple(
        (method, details["label"])
        for method, details in PAYMENT_METHOD_REGISTRY.items()
        if details["available"]
    )
