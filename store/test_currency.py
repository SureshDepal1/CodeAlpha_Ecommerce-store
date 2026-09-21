from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from .money import format_money


class CurrencyFormattingTests(SimpleTestCase):
    def test_default_format_matches_existing_output(self):
        self.assertEqual(format_money(Decimal("75")), "$75.00")
        self.assertEqual(format_money(Decimal("12.345")), "$12.35")

    @override_settings(STORE_PRICE_FORMAT="Rs. {amount}", STORE_CURRENCY_CODE="PKR")
    def test_custom_format_is_used_by_python_and_template_helpers(self):
        self.assertEqual(format_money(Decimal("1250")), "Rs. 1250.00")
        output = Template("{% load store_tags %}{{ value|money }}").render(Context({"value": Decimal("1250")}))
        self.assertEqual(output, "Rs. 1250.00")

    @override_settings(STORE_PRICE_FORMAT="invalid")
    def test_invalid_runtime_format_falls_back(self):
        self.assertEqual(format_money(Decimal("10")), "$10.00")

    @override_settings(TIME_ZONE="Asia/Karachi")
    def test_dates_render_in_configured_timezone(self):
        value = timezone.make_aware(datetime(2026, 9, 21, 20, 0), datetime_timezone.utc)
        with timezone.override("Asia/Karachi"):
            output = Template('{{ value|date:"F j, Y, g:i a" }}').render(Context({"value": value}))
        self.assertEqual(output, "September 22, 2026, 1:00 a.m.")
