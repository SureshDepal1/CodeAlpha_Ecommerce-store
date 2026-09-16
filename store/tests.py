from django.test import TestCase

from .models import Product


class HomePageTests(TestCase):
    def test_homepage_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "store/home.html")


class ProductModelTests(TestCase):
    def test_product_can_be_created(self):
        product = Product.objects.create(
            name="Wireless Headphones",
            description="Comfortable wireless headphones.",
            price="4999.00",
            category="Electronics",
        )

        self.assertIsNotNone(product.pk)

    def test_product_str_returns_name(self):
        product = Product.objects.create(
            name="Mechanical Keyboard",
            description="A responsive mechanical keyboard.",
            price="7500.00",
            category="Electronics",
        )

        self.assertEqual(str(product), "Mechanical Keyboard")

    def test_stock_defaults_to_zero(self):
        product = Product.objects.create(
            name="Cotton T-Shirt",
            description="A comfortable cotton t-shirt.",
            price="1999.00",
            category="Clothing",
        )

        self.assertEqual(product.stock, 0)

    def test_is_available_defaults_to_true(self):
        product = Product.objects.create(
            name="Desk Lamp",
            description="A compact desk lamp.",
            price="999.99",
            category="Home",
        )

        self.assertTrue(product.is_available)
