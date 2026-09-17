from django.test import TestCase

from .models import Product


class HomePageTests(TestCase):
    def test_homepage_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "store/home.html")


class ProductListingTests(TestCase):
    def create_product(self, name, is_available=True, stock=5):
        return Product.objects.create(
            name=name,
            description=f"Description for {name}.",
            price="1999.99",
            category="General",
            stock=stock,
            is_available=is_available,
        )

    def test_product_listing_loads(self):
        response = self.client.get("/products/")

        self.assertEqual(response.status_code, 200)

    def test_available_product_appears_in_listing(self):
        self.create_product("Available Product")

        response = self.client.get("/products/")

        self.assertContains(response, "Available Product")

    def test_unavailable_product_does_not_appear_in_listing(self):
        self.create_product("Unavailable Product", is_available=False)

        response = self.client.get("/products/")

        self.assertNotContains(response, "Unavailable Product")

    def test_multiple_products_are_displayed(self):
        self.create_product("First Product")
        self.create_product("Second Product")

        response = self.client.get("/products/")

        self.assertContains(response, "First Product")
        self.assertContains(response, "Second Product")

    def test_product_listing_uses_correct_template(self):
        response = self.client.get("/products/")

        self.assertTemplateUsed(response, "store/product_list.html")

    def test_empty_listing_shows_empty_state(self):
        response = self.client.get("/products/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No products are available at the moment.")

    def test_out_of_stock_product_shows_stock_state(self):
        self.create_product("Sold Out Product", stock=0)

        response = self.client.get("/products/")

        self.assertContains(response, "Out of Stock")


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
