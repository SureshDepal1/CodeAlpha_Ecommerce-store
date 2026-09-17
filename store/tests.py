from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse

from .models import Product


User = get_user_model()


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

    def test_view_details_link_points_to_product_detail(self):
        product = self.create_product("Detail Link Product")

        response = self.client.get(reverse("store:product_list"))

        self.assertContains(
            response,
            f'href="{reverse("store:product_detail", args=[product.pk])}"',
        )


class ProductDetailTests(TestCase):
    def create_product(self, **overrides):
        product_data = {
            "name": "Detail Product",
            "description": "A detailed product description.",
            "price": "2499.50",
            "category": "Featured",
            "stock": 20,
            "is_available": True,
        }
        product_data.update(overrides)
        return Product.objects.create(**product_data)

    def test_available_product_detail_loads(self):
        product = self.create_product()

        response = self.client.get(reverse("store:product_detail", args=[product.pk]))

        self.assertEqual(response.status_code, 200)

    def test_product_details_are_displayed(self):
        product = self.create_product()

        response = self.client.get(reverse("store:product_detail", args=[product.pk]))

        self.assertContains(response, product.name)
        self.assertContains(response, product.description)
        self.assertContains(response, "2499.50")
        self.assertContains(response, product.category)

    def test_product_detail_uses_correct_template(self):
        product = self.create_product()

        response = self.client.get(reverse("store:product_detail", args=[product.pk]))

        self.assertTemplateUsed(response, "store/product_detail.html")

    def test_nonexistent_product_returns_404(self):
        response = self.client.get(reverse("store:product_detail", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_unavailable_product_returns_404(self):
        product = self.create_product(is_available=False)

        response = self.client.get(reverse("store:product_detail", args=[product.pk]))

        self.assertEqual(response.status_code, 404)

    def test_in_stock_status_is_displayed(self):
        product = self.create_product(stock=3)

        response = self.client.get(reverse("store:product_detail", args=[product.pk]))

        self.assertContains(response, "In Stock")
        self.assertContains(response, "3 items available")

    def test_out_of_stock_status_is_displayed(self):
        product = self.create_product(stock=0)

        response = self.client.get(reverse("store:product_detail", args=[product.pk]))

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


class RegistrationTests(TestCase):
    registration_url = reverse("store:register")
    valid_registration_data = {
        "username": "newshopper",
        "email": "newshopper@example.com",
        "password1": "A-strong-registration-password-123!",
        "password2": "A-strong-registration-password-123!",
    }

    def test_registration_page_loads(self):
        response = self.client.get(self.registration_url)

        self.assertEqual(response.status_code, 200)

    def test_registration_uses_correct_template(self):
        response = self.client.get(self.registration_url)

        self.assertTemplateUsed(response, "store/register.html")

    def test_registration_form_contains_expected_fields_and_csrf_token(self):
        response = self.client.get(self.registration_url)

        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_valid_registration_creates_user_with_hashed_password(self):
        response = self.client.post(
            self.registration_url,
            self.valid_registration_data,
            follow=True,
        )

        user = User.objects.get(username="newshopper")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(reverse("store:home"), 302)])
        self.assertContains(response, "Account created successfully.")
        self.assertNotEqual(user.password, self.valid_registration_data["password1"])
        self.assertTrue(check_password(self.valid_registration_data["password1"], user.password))

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username="newshopper", password="ExistingPassword123!")

        response = self.client.post(self.registration_url, self.valid_registration_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists.")
        self.assertEqual(User.objects.filter(username="newshopper").count(), 1)

    def test_password_confirmation_mismatch_is_rejected(self):
        invalid_data = self.valid_registration_data | {"password2": "DifferentPassword123!"}

        response = self.client.post(self.registration_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match.")
        self.assertFalse(User.objects.filter(username="newshopper").exists())

    def test_invalid_email_is_rejected(self):
        invalid_data = self.valid_registration_data | {"email": "not-an-email"}

        response = self.client.post(self.registration_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address.")
        self.assertFalse(User.objects.filter(username="newshopper").exists())

    def test_invalid_form_does_not_create_user(self):
        invalid_data = self.valid_registration_data | {"username": ""}

        response = self.client.post(self.registration_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newshopper@example.com").exists())
