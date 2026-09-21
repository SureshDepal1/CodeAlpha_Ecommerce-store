from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging

from django.conf import settings

logger = logging.getLogger("store")


def format_money(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0.00")
    price_format = settings.STORE_PRICE_FORMAT
    if "{amount}" not in price_format:
        logger.warning("STORE_PRICE_FORMAT must contain {amount}; using ${amount}.")
        price_format = "${amount}"
    return price_format.format(amount=f"{amount:.2f}")
