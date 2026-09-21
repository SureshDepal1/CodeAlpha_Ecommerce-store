from decimal import Decimal
from importlib import import_module
from unittest.mock import Mock

from django.contrib import admin
from django.test import TestCase, override_settings
from django.urls import reverse
from .admin import OrderAdmin
from .forms import CheckoutForm
from .models import Order, Product
from .pricing import calculate_totals


backfill_order_subtotals = import_module(
    "store.migrations.0004_order_paid_at_order_payment_method_and_more"
).backfill_order_subtotals


class PricingTests(TestCase):
    @override_settings(
        SHIPPING_FLAT_RATE=Decimal("10.00"),
        FREE_SHIPPING_THRESHOLD=Decimal("100.00"),
        TAX_RATE_PERCENT=Decimal("8.875"),
    )
    def test_shipping_threshold_and_tax_round_half_up(self):
        self.assertEqual(
            calculate_totals(Decimal("99.99")),
            {
                "subtotal": Decimal("99.99"),
                "shipping_cost": Decimal("10.00"),
                "tax_amount": Decimal("8.87"),
                "total": Decimal("118.86"),
            },
        )
        self.assertEqual(calculate_totals(Decimal("100.00"))["shipping_cost"], Decimal("0.00"))

    def test_default_pricing_preserves_existing_total(self):
        self.assertEqual(calculate_totals(Decimal("261.25"))["total"], Decimal("261.25"))


class PaymentTests(TestCase):
    def test_only_cash_on_delivery_is_available(self):
        form = CheckoutForm({"payment_method": "card"})
        self.assertFalse(form.is_valid())
        self.assertIn("Select a valid choice", str(form.errors))

    def test_missing_payment_method_defaults_to_cod(self):
        form = CheckoutForm(
            {
                "full_name": "Customer",
                "email": "customer@example.com",
                "phone": "1",
                "address": "Street",
                "city": "City",
                "state": "State",
                "postal_code": "1",
                "country": "Country",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["payment_method"], "cod")


class TamperedCheckoutTests(TestCase):
    def test_submitted_totals_are_ignored(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username="tampered", password="StrongPassword123!")
        product = Product.objects.create(
            name="Tamper Test Product",
            description="A product.",
            price=Decimal("25.00"),
            category="General",
            stock=2,
            is_available=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["cart"] = {str(product.pk): 1}
        session.save()

        response = self.client.post(
            reverse("store:checkout"),
            {
                "full_name": "Customer",
                "email": "customer@example.com",
                "phone": "1",
                "address": "Street",
                "city": "City",
                "state": "State",
                "postal_code": "1",
                "country": "Country",
                "review_only": "1",
                "subtotal": "1.00",
                "shipping_cost": "999.00",
                "tax_amount": "999.00",
                "total_amount": "1.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.subtotal, Decimal("25.00"))
        self.assertEqual(order.shipping_cost, Decimal("0.00"))
        self.assertEqual(order.tax_amount, Decimal("0.00"))
        self.assertEqual(order.total_amount, Decimal("25.00"))


class AdminPaymentActionTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            user_id=self._create_user(),
            full_name="Admin Customer",
            email="admin@example.com",
            phone="1",
            address="Street",
            city="City",
            state="State",
            postal_code="1",
            country="Country",
            total_amount=Decimal("10.00"),
        )
        self.admin = OrderAdmin(Order, admin.site)

    def _create_user(self):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username="admin-action", password="StrongPassword123!").pk

    def test_mark_paid_and_unpaid_actions(self):
        queryset = Order.objects.filter(pk=self.order.pk)
        self.admin.mark_selected_as_paid(None, queryset)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNotNone(self.order.paid_at)

        self.admin.mark_selected_as_unpaid(None, queryset)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)
        self.assertIsNone(self.order.paid_at)


class MigrationBackfillTests(TestCase):
    def test_backfill_copies_total_to_subtotal(self):
        manager = Mock()
        apps = Mock()
        apps.get_model.return_value.objects = manager

        backfill_order_subtotals(apps, None)

        manager.all.return_value.update.assert_called_once()
        update_kwargs = manager.all.return_value.update.call_args.kwargs
        self.assertEqual(str(update_kwargs["subtotal"]), "F(total_amount)")
