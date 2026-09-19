from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.hashers import check_password
from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from .management.commands import seed_demo_products
from .models import Order, OrderItem, Product
from .views import custom_500


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

    def create_filter_product(self, name, description, category, price, stock=5, is_available=True):
        return Product.objects.create(
            name=name,
            description=description,
            category=category,
            price=price,
            stock=stock,
            is_available=is_available,
        )

    def test_search_matches_name_case_insensitively(self):
        self.create_filter_product("Laptop Pro", "Fast computer", "Electronics", "1200.00")
        self.create_filter_product("Desk", "Office furniture", "Home", "500.00")

        response = self.client.get(reverse("store:product_list"), {"q": "LAPTOP"})

        self.assertContains(response, "Laptop Pro")
        self.assertNotContains(response, "Desk")

    def test_search_matches_description_and_category(self):
        self.create_filter_product("Travel Kit", "Lightweight camping gear", "Outdoor", "80.00")
        self.create_filter_product("Office Chair", "Comfortable seat", "Furniture", "150.00")

        description_response = self.client.get(reverse("store:product_list"), {"q": "camping"})
        category_response = self.client.get(reverse("store:product_list"), {"q": "outdoor"})

        self.assertContains(description_response, "Travel Kit")
        self.assertContains(category_response, "Travel Kit")
        self.assertNotContains(description_response, "Office Chair")

    def test_search_does_not_show_unavailable_products(self):
        self.create_filter_product("Hidden Laptop", "A laptop", "Electronics", "1200.00", is_available=False)

        response = self.client.get(reverse("store:product_list"), {"q": "laptop"})

        self.assertNotContains(response, "Hidden Laptop")

    def test_category_filter_is_case_insensitive_and_categories_are_unique(self):
        self.create_filter_product("Phone", "Smart phone", "Electronics", "700.00")
        self.create_filter_product("Cable", "Phone cable", "electronics", "20.00")
        self.create_filter_product("Table", "Wood table", "Home", "300.00")

        response = self.client.get(reverse("store:product_list"), {"category": "ELECTRONICS"})

        self.assertContains(response, "Phone")
        self.assertContains(response, "Cable")
        self.assertNotContains(response, "Table")
        self.assertEqual(response.context["categories"], ["Electronics", "Home"])

    def test_invalid_category_is_safe_and_returns_no_products(self):
        self.create_filter_product("Phone", "Smart phone", "Electronics", "700.00")

        response = self.client.get(reverse("store:product_list"), {"category": "Unknown"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No products found matching your filters.")
        self.assertEqual(response.context["result_count"], 0)

    def test_price_filters_support_minimum_maximum_and_decimals(self):
        self.create_filter_product("Budget", "Budget item", "General", "10.25")
        self.create_filter_product("Midrange", "Midrange item", "General", "50.50")
        self.create_filter_product("Premium", "Premium item", "General", "100.75")

        response = self.client.get(
            reverse("store:product_list"),
            {"min_price": "10.25", "max_price": "50.50"},
        )

        self.assertContains(response, "Budget")
        self.assertContains(response, "Midrange")
        self.assertNotContains(response, "Premium")

    def test_invalid_and_negative_price_values_do_not_crash(self):
        self.create_filter_product("Valid Product", "Valid", "General", "25.00")

        response = self.client.get(
            reverse("store:product_list"),
            {"min_price": "abc", "max_price": "NaN"},
        )
        negative_response = self.client.get(
            reverse("store:product_list"),
            {"min_price": "-10"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(negative_response.status_code, 200)
        self.assertContains(response, "Please enter a valid minimum price.")
        self.assertContains(response, "Please enter a valid maximum price.")
        self.assertContains(negative_response, "Please enter a valid minimum price.")

    def test_minimum_price_greater_than_maximum_returns_empty_state(self):
        self.create_filter_product("Product", "Product", "General", "25.00")

        response = self.client.get(
            reverse("store:product_list"),
            {"min_price": "100", "max_price": "10"},
        )

        self.assertEqual(response.context["result_count"], 0)
        self.assertContains(response, "Minimum price cannot be greater than maximum price.")
        self.assertContains(response, "No products found matching your filters.")

    def test_availability_filter_only_uses_available_products(self):
        self.create_filter_product("Available Stock", "In stock", "General", "20.00", stock=2)
        self.create_filter_product("Available Sold Out", "Out of stock", "General", "30.00", stock=0)
        self.create_filter_product("Unavailable Stock", "Hidden", "General", "40.00", stock=2, is_available=False)

        in_stock = self.client.get(reverse("store:product_list"), {"availability": "in_stock"})
        out_of_stock = self.client.get(reverse("store:product_list"), {"availability": "out_of_stock"})

        self.assertContains(in_stock, "Available Stock")
        self.assertNotContains(in_stock, "Available Sold Out")
        self.assertContains(out_of_stock, "Available Sold Out")
        self.assertNotContains(out_of_stock, "Unavailable Stock")

    def test_sorting_options_and_invalid_sort_are_safe(self):
        first = self.create_filter_product("Zeta", "Z", "General", "30.00")
        second = self.create_filter_product("Alpha", "A", "General", "10.00")
        third = self.create_filter_product("Middle", "M", "General", "20.00")
        Product.objects.filter(pk=first.pk).update(created_at="2026-09-17T12:00:00Z")
        Product.objects.filter(pk=second.pk).update(created_at="2026-09-18T12:00:00Z")
        Product.objects.filter(pk=third.pk).update(created_at="2026-09-16T12:00:00Z")

        low_response = self.client.get(reverse("store:product_list"), {"sort": "price_low"})
        high_response = self.client.get(reverse("store:product_list"), {"sort": "price_high"})
        name_response = self.client.get(reverse("store:product_list"), {"sort": "name_az"})
        invalid_response = self.client.get(reverse("store:product_list"), {"sort": "created_at"})

        self.assertEqual(list(low_response.context["products"]), [second, third, first])
        self.assertEqual(list(high_response.context["products"]), [first, third, second])
        self.assertEqual(list(name_response.context["products"]), [second, third, first])
        self.assertEqual(invalid_response.context["filters"]["sort"], "newest")
        self.assertEqual(list(invalid_response.context["products"]), [second, first, third])

    def test_combined_filters_and_sorting_work_together(self):
        self.create_filter_product("Phone Mini", "Compact phone", "Electronics", "300.00")
        self.create_filter_product("Phone Max", "Large phone", "Electronics", "900.00")
        self.create_filter_product("Phone Case", "Protective case", "Accessories", "30.00")

        response = self.client.get(
            reverse("store:product_list"),
            {
                "q": "phone",
                "category": "electronics",
                "min_price": "200",
                "max_price": "500",
                "sort": "price_high",
            },
        )

        self.assertContains(response, "Phone Mini")
        self.assertNotContains(response, "Phone Max")
        self.assertNotContains(response, "Phone Case")
        self.assertEqual(response.context["result_count"], 1)

    def test_filter_controls_results_count_and_clear_link_are_present(self):
        self.create_filter_product("Visible Product", "Description", "General", "25.00")

        response = self.client.get(reverse("store:product_list"), {"q": "Visible"})

        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="min_price"')
        self.assertContains(response, 'name="max_price"')
        self.assertContains(response, 'name="availability"')
        self.assertContains(response, 'name="sort"')
        self.assertContains(response, "1 product found")
        self.assertContains(response, f'href="{reverse("store:product_list")}"')
        self.assertContains(response, "Visible Product")


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


class DemoSeedCommandTests(TestCase):
    def test_seed_demo_products_is_idempotent(self):
        names = [item["name"] for item in seed_demo_products.DEMO_BLUEPRINTS[:3]]

        call_command("seed_demo_products", count=3, no_images=True)
        first_count = Product.objects.filter(name__in=names).count()

        call_command("seed_demo_products", count=3, no_images=True)
        second_count = Product.objects.filter(name__in=names).count()

        self.assertEqual(first_count, 3)
        self.assertEqual(second_count, 3)

    def test_clear_demo_products_only_removes_seeded_items(self):
        seeded_names = [item["name"] for item in seed_demo_products.DEMO_BLUEPRINTS[:2]]
        Product.objects.create(
            name="Legitimate Real Product",
            description="Real product that should stay.",
            price="24.99",
            category="General",
            stock=10,
            is_available=True,
        )

        call_command("seed_demo_products", count=2, no_images=True)
        call_command("seed_demo_products", count=2, no_images=True, clear_demo=True)

        self.assertFalse(Product.objects.filter(name__in=seeded_names).exists())
        self.assertTrue(Product.objects.filter(name="Legitimate Real Product").exists())


class AuthenticationTests(TestCase):
    login_url = reverse("store:login")
    logout_url = reverse("store:logout")

    def setUp(self):
        self.username = "existing-shopper"
        self.password = "A-valid-login-password-123!"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
        )

    def test_login_page_loads(self):
        response = self.client.get(self.login_url)

        self.assertEqual(response.status_code, 200)

    def test_login_uses_correct_template(self):
        response = self.client.get(self.login_url)

        self.assertTemplateUsed(response, "store/login.html")

    def test_login_form_contains_username_password_and_csrf(self):
        response = self.client.get(self.login_url)

        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'type="password"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_valid_login_authenticates_user_and_redirects_home(self):
        response = self.client.post(
            self.login_url,
            {"username": self.username, "password": self.password},
        )

        self.assertRedirects(response, reverse("store:home"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_credentials_do_not_authenticate_user(self):
        response = self.client.post(
            self.login_url,
            {"username": self.username, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "Please enter a correct username and password.")

    def test_nonexistent_username_does_not_authenticate_user(self):
        response = self.client.post(
            self.login_url,
            {"username": "does-not-exist", "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_anonymous_navigation_contains_login_and_register(self):
        response = self.client.get(reverse("store:home"))

        self.assertContains(response, f'href="{self.login_url}"')
        self.assertContains(response, f'href="{reverse("store:register")}"')
        self.assertNotContains(response, "Welcome, existing-shopper")

    def test_authenticated_navigation_contains_logout(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:home"))

        self.assertContains(response, f'action="{self.logout_url}"')
        self.assertContains(response, "Logout")
        self.assertContains(response, "Welcome, existing-shopper")
        self.assertNotContains(response, f'href="{self.login_url}"')

    def test_logout_logs_user_out_and_redirects_home(self):
        self.client.force_login(self.user)

        response = self.client.post(self.logout_url)

        self.assertRedirects(response, reverse("store:home"))
        homepage = self.client.get(reverse("store:home"))
        self.assertContains(homepage, f'href="{self.login_url}"')
        self.assertNotContains(homepage, "Welcome, existing-shopper")

    def test_get_logout_does_not_log_user_out(self):
        self.client.force_login(self.user)

        response = self.client.get(self.logout_url)

        self.assertRedirects(response, reverse("store:home"))
        homepage = self.client.get(reverse("store:home"))
        self.assertContains(homepage, "Logout")


class CartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cartuser", password="StrongPassword123!")
        self.product_a = Product.objects.create(
            name="Product A",
            description="A sample product.",
            price="100.00",
            category="General",
            stock=5,
            is_available=True,
        )
        self.product_b = Product.objects.create(
            name="Product B",
            description="Another sample product.",
            price="50.00",
            category="General",
            stock=3,
            is_available=True,
        )
        self.cart_url = reverse("store:cart")
        self.add_to_cart_url = reverse("store:add_to_cart", args=[self.product_a.pk])

    def test_authenticated_user_can_access_cart(self):
        self.client.force_login(self.user)

        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_accessing_cart_is_redirected_to_login(self):
        response = self.client.get(self.cart_url)

        self.assertRedirects(response, f"{reverse('store:login')}?next={self.cart_url}")

    def test_authenticated_user_can_add_available_product(self):
        self.client.force_login(self.user)

        response = self.client.post(self.add_to_cart_url)

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session.get("cart", {}), {str(self.product_a.pk): 1})

    def test_adding_same_product_twice_increases_quantity(self):
        self.client.force_login(self.user)

        self.client.post(self.add_to_cart_url)
        self.client.post(self.add_to_cart_url)

        self.assertEqual(self.client.session.get("cart", {}), {str(self.product_a.pk): 2})

    def test_adding_a_product_cannot_exceed_available_stock(self):
        self.product_a.stock = 2
        self.product_a.save()
        self.client.force_login(self.user)

        self.client.post(self.add_to_cart_url)
        self.client.post(self.add_to_cart_url)
        self.client.post(self.add_to_cart_url)

        self.assertEqual(self.client.session.get("cart", {}), {str(self.product_a.pk): 2})

    def test_out_of_stock_product_cannot_be_added(self):
        self.product_a.stock = 0
        self.product_a.save()
        self.client.force_login(self.user)

        response = self.client.post(self.add_to_cart_url)

        self.assertRedirects(response, self.cart_url)
        self.assertNotIn(str(self.product_a.pk), self.client.session.get("cart", {}))

    def test_unavailable_product_cannot_be_added(self):
        self.product_a.is_available = False
        self.product_a.save()
        self.client.force_login(self.user)

        response = self.client.post(self.add_to_cart_url)

        self.assertRedirects(response, self.cart_url)
        self.assertNotIn(str(self.product_a.pk), self.client.session.get("cart", {}))

    def test_nonexistent_product_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("store:add_to_cart", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_add_a_product_to_cart(self):
        response = self.client.post(self.add_to_cart_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_cart_page_displays_product_name(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, self.product_a.name)

    def test_cart_page_displays_product_price(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, "100.00")

    def test_cart_page_displays_quantity(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, "2")

    def test_cart_page_displays_subtotal(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, "200.00")

    def test_cart_page_calculates_total_correctly(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2, str(self.product_b.pk): 1}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, "250.00")

    def test_empty_cart_displays_empty_cart_message(self):
        self.client.force_login(self.user)

        response = self.client.get(self.cart_url)

        self.assertContains(response, "Your cart is empty.")

    def test_cart_count_is_correct(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2, str(self.product_b.pk): 3}
        session.save()

        response = self.client.get(reverse("store:home"))

        self.assertContains(response, "Cart (5)")

    def test_cart_count_is_zero_when_cart_is_empty(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:home"))

        self.assertContains(response, "Cart (0)")

    def test_product_price_comes_from_database_not_session(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()
        self.product_a.price = "250.00"
        self.product_a.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, "250.00")

    def test_unavailable_product_in_session_does_not_crash_cart_page(self):
        self.client.force_login(self.user)
        self.product_a.is_available = False
        self.product_a.save()
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your cart is empty.")

    def test_add_to_cart_requires_post(self):
        self.client.force_login(self.user)

        response = self.client.get(self.add_to_cart_url)

        self.assertEqual(response.status_code, 405)


class CartManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cartmanager", password="StrongPassword123!")
        self.product = Product.objects.create(
            name="Manageable Product",
            description="A product for inventory management.",
            price="15.00",
            category="General",
            stock=5,
            is_available=True,
        )
        self.product_with_2_stock = Product.objects.create(
            name="Limited Product",
            description="Only a few left.",
            price="9.00",
            category="General",
            stock=2,
            is_available=True,
        )
        self.cart_url = reverse("store:cart")
        self.update_url = reverse("store:update_cart", args=[self.product.pk])
        self.increase_url = reverse("store:increase_cart_quantity", args=[self.product.pk])
        self.decrease_url = reverse("store:decrease_cart_quantity", args=[self.product.pk])
        self.remove_url = reverse("store:remove_from_cart", args=[self.product.pk])

    def test_authenticated_user_can_update_cart_quantity(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()

        response = self.client.post(self.update_url, {"quantity": 3})

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 3)

    def test_update_quantity_cannot_exceed_stock(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()

        response = self.client.post(self.update_url, {"quantity": 10})

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], self.product.stock)

    def test_update_quantity_rejects_zero(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()

        response = self.client.post(self.update_url, {"quantity": 0})

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 1)

    def test_update_quantity_rejects_negative_values(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.post(self.update_url, {"quantity": -2})

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 2)

    def test_update_quantity_rejects_non_numeric_values(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.post(self.update_url, {"quantity": "abc"})

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 2)

    def test_update_quantity_requires_authentication(self):
        response = self.client.post(self.update_url, {"quantity": 3})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_increase_quantity_works(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()

        response = self.client.post(self.increase_url)

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 2)

    def test_increase_quantity_cannot_exceed_stock(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_with_2_stock.pk): 2}
        session.save()

        response = self.client.post(reverse("store:increase_cart_quantity", args=[self.product_with_2_stock.pk]))

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product_with_2_stock.pk)], 2)

    def test_increase_quantity_requires_authentication(self):
        response = self.client.post(self.increase_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_decrease_quantity_works(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 3}
        session.save()

        response = self.client.post(self.decrease_url)

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 2)

    def test_decrease_from_one_removes_item(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()

        response = self.client.post(self.decrease_url)

        self.assertRedirects(response, self.cart_url)
        self.assertNotIn(str(self.product.pk), self.client.session.get("cart", {}))

    def test_decrease_quantity_requires_authentication(self):
        response = self.client.post(self.decrease_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_remove_item_works(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2, str(self.product_with_2_stock.pk): 1}
        session.save()

        response = self.client.post(self.remove_url)

        self.assertRedirects(response, self.cart_url)
        self.assertNotIn(str(self.product.pk), self.client.session.get("cart", {}))

    def test_removing_item_updates_cart_count(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2, str(self.product_with_2_stock.pk): 1}
        session.save()

        self.client.post(self.remove_url)

        self.assertEqual(sum(self.client.session["cart"].values()), 1)

    def test_remove_requires_authentication(self):
        response = self.client.post(self.remove_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_cart_page_displays_quantity_controls(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, "Update")
        self.assertContains(response, "Remove")
        self.assertContains(response, 'name="quantity"')

    def test_cart_calculates_subtotal_and_total_correctly(self):
        self.client.force_login(self.user)
        self.product_with_2_stock.stock = 3
        self.product_with_2_stock.save()
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2, str(self.product_with_2_stock.pk): 3}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertContains(response, "30.00")
        self.assertContains(response, "57.00")

    def test_cart_count_is_correct_after_update(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()

        self.client.post(self.update_url, {"quantity": 4})

        self.assertEqual(sum(self.client.session["cart"].values()), 4)

    def test_cart_count_is_correct_after_increase(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()

        self.client.post(self.increase_url)

        self.assertEqual(sum(self.client.session["cart"].values()), 2)

    def test_cart_count_is_correct_after_decrease(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 3}
        session.save()

        self.client.post(self.decrease_url)

        self.assertEqual(sum(self.client.session["cart"].values()), 2)

    def test_cart_count_is_correct_after_removal(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2, str(self.product_with_2_stock.pk): 1}
        session.save()

        self.client.post(self.remove_url)

        self.assertEqual(sum(self.client.session["cart"].values()), 1)

    def test_cart_mutation_endpoints_require_post(self):
        self.client.force_login(self.user)

        self.assertEqual(self.client.get(self.update_url).status_code, 405)
        self.assertEqual(self.client.get(self.increase_url).status_code, 405)
        self.assertEqual(self.client.get(self.decrease_url).status_code, 405)
        self.assertEqual(self.client.get(self.remove_url).status_code, 405)

    def test_nonexistent_product_id_is_handled_safely(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("store:update_cart", args=[999999]), {"quantity": 2})

        self.assertEqual(response.status_code, 404)

    def test_malformed_cart_data_does_not_crash(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): "abc", "notanumber": "3", "999": 0}
        session.save()

        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your cart is empty.")


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="checkoutuser",
            password="StrongPassword123!",
            email="checkoutuser@example.com",
        )
        self.product_a = Product.objects.create(
            name="Checkout Product A",
            description="A checkout item.",
            price="100.00",
            category="General",
            stock=5,
            is_available=True,
        )
        self.product_b = Product.objects.create(
            name="Checkout Product B",
            description="Another checkout item.",
            price="50.00",
            category="General",
            stock=3,
            is_available=True,
        )
        self.checkout_url = reverse("store:checkout")

    def test_authenticated_user_can_access_checkout(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_accessing_checkout_is_redirected_to_login(self):
        response = self.client.get(self.checkout_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_empty_cart_cannot_proceed_to_checkout(self):
        self.client.force_login(self.user)

        response = self.client.get(self.checkout_url)

        self.assertRedirects(response, reverse("store:cart"))

    def test_empty_cart_displays_message_when_redirected(self):
        self.client.force_login(self.user)

        response = self.client.get(self.checkout_url)
        follow_response = self.client.get(reverse("store:cart"))

        self.assertEqual(response.status_code, 302)
        self.assertContains(follow_response, "Your cart is empty.")

    def test_checkout_form_contains_expected_fields(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, 'name="full_name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="phone"')
        self.assertContains(response, 'name="address"')
        self.assertContains(response, 'name="city"')
        self.assertContains(response, 'name="state"')
        self.assertContains(response, 'name="postal_code"')
        self.assertContains(response, 'name="country"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_full_name_is_required(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.post(
            self.checkout_url,
            {
                "full_name": "",
                "email": "user@example.com",
                "phone": "03001234567",
                "address": "123 Main Street",
                "city": "Karachi",
                "state": "Sindh",
                "postal_code": "74000",
                "country": "Pakistan",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    def test_email_is_required(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.post(
            self.checkout_url,
            {
                "full_name": "Test User",
                "email": "",
                "phone": "03001234567",
                "address": "123 Main Street",
                "city": "Karachi",
                "state": "Sindh",
                "postal_code": "74000",
                "country": "Pakistan",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    def test_invalid_email_is_rejected(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.post(
            self.checkout_url,
            {
                "full_name": "Test User",
                "email": "not-an-email",
                "phone": "03001234567",
                "address": "123 Main Street",
                "city": "Karachi",
                "state": "Sindh",
                "postal_code": "74000",
                "country": "Pakistan",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address.")

    def test_phone_is_required(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.post(
            self.checkout_url,
            {
                "full_name": "Test User",
                "email": "user@example.com",
                "phone": "",
                "address": "123 Main Street",
                "city": "Karachi",
                "state": "Sindh",
                "postal_code": "74000",
                "country": "Pakistan",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    def test_address_is_required(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.post(
            self.checkout_url,
            {
                "full_name": "Test User",
                "email": "user@example.com",
                "phone": "03001234567",
                "address": "",
                "city": "Karachi",
                "state": "Sindh",
                "postal_code": "74000",
                "country": "Pakistan",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    def test_valid_checkout_data_passes_form_validation(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2, str(self.product_b.pk): 1}
        session.save()

        response = self.client.post(
            self.checkout_url,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "03001234567",
                "address": "123 Test Street",
                "city": "Karachi",
                "state": "Sindh",
                "postal_code": "74000",
                "country": "Pakistan",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review Your Order")
        self.assertContains(response, "Test User")

    def test_user_email_is_prefilled_on_checkout_form(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, 'value="checkoutuser@example.com"')

    def test_checkout_displays_product_name_and_quantity(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, self.product_a.name)
        self.assertContains(response, "2")

    def test_checkout_displays_product_price_and_subtotal(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, "100.00")
        self.assertContains(response, "200.00")

    def test_checkout_calculates_total_correctly(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2, str(self.product_b.pk): 3}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, "350.00")

    def test_checkout_total_comes_from_database_prices(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()
        self.product_a.price = "250.00"
        self.product_a.save()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, "250.00")

    def test_checkout_blocks_when_cart_quantity_exceeds_stock(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 5}
        session.save()
        self.product_a.stock = 2
        self.product_a.save()

        response = self.client.get(self.checkout_url)

        self.assertEqual(response.status_code, 302)

    def test_checkout_blocks_unavailable_product(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()
        self.product_a.is_available = False
        self.product_a.save()

        response = self.client.get(self.checkout_url)

        self.assertEqual(response.status_code, 302)

    def test_checkout_handles_stale_cart_product_safely(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1, "999": 2}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertEqual(response.status_code, 200)

    def test_checkout_post_requires_post(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertEqual(response.status_code, 200)

    def test_checkout_form_has_csrf_protection(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 1}
        session.save()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, "csrfmiddlewaretoken")

    def test_valid_checkout_submission_keeps_cart_and_stock_unchanged(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product_a.pk): 2}
        session.save()
        original_stock = self.product_a.stock

        response = self.client.post(
            self.checkout_url,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "03001234567",
                "address": "123 Test Street",
                "city": "Karachi",
                "state": "Sindh",
                "postal_code": "74000",
                "country": "Pakistan",
            },
        )

        self.product_a.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["cart"][str(self.product_a.pk)], 2)
        self.assertEqual(self.product_a.stock, original_stock)


class OrderProcessingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="orderuser",
            password="StrongPassword123!",
            email="orderuser@example.com",
        )
        self.other_user = User.objects.create_user(username="otheruser", password="StrongPassword123!")
        self.product = Product.objects.create(
            name="Order Product",
            description="A product for order tests.",
            price="125.50",
            category="General",
            stock=5,
            is_available=True,
        )
        self.second_product = Product.objects.create(
            name="Second Order Product",
            description="Another product for order tests.",
            price="10.25",
            category="General",
            stock=4,
            is_available=True,
        )
        self.checkout_url = reverse("store:checkout")
        self.checkout_data = {
            "full_name": "Order Customer",
            "email": "customer@example.com",
            "phone": "03001234567",
            "address": "123 Test Street",
            "city": "Karachi",
            "state": "Sindh",
            "postal_code": "74000",
            "country": "Pakistan",
            "review_only": "1",
        }

    def set_cart(self, cart):
        session = self.client.session
        session["cart"] = cart
        session.save()

    def place_order(self, cart=None):
        self.client.force_login(self.user)
        self.set_cart(cart or {str(self.product.pk): 2})
        return self.client.post(self.checkout_url, self.checkout_data)

    def test_order_and_order_item_store_correct_values(self):
        response = self.place_order({str(self.product.pk): 2, str(self.second_product.pk): 1})

        order = Order.objects.get()
        item = order.items.get(product=self.product)
        self.assertRedirects(response, reverse("store:order_confirmation", args=[order.pk]))
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total_amount, Decimal("261.25"))
        self.assertIsNotNone(order.created_at)
        self.assertIsNotNone(order.updated_at)
        self.assertEqual(item.product_name, "Order Product")
        self.assertEqual(item.price, Decimal("125.50"))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.subtotal, Decimal("251.00"))

    def test_order_stock_is_reduced_and_cart_is_cleared(self):
        self.place_order()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.client.session.get("cart"), {})

    def test_buying_all_stock_marks_product_unavailable(self):
        self.place_order({str(self.product.pk): 5})

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertFalse(self.product.is_available)

    def test_historical_product_name_and_price_are_preserved(self):
        self.place_order()
        item = OrderItem.objects.get()
        self.product.name = "Renamed Product"
        self.product.price = Decimal("999.99")
        self.product.save()

        item.refresh_from_db()
        self.assertEqual(item.product_name, "Order Product")
        self.assertEqual(item.price, Decimal("125.50"))

    def test_unavailable_or_insufficient_stock_keeps_cart_and_creates_no_order(self):
        self.product.stock = 1
        self.product.save()
        response = self.place_order({str(self.product.pk): 2})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 2})
        self.assertEqual(response.url, reverse("store:cart"))

    def test_deleted_product_keeps_cart_and_creates_no_order(self):
        self.client.force_login(self.user)
        product_id = self.product.pk
        self.set_cart({str(product_id): 1})
        self.product.delete()

        response = self.client.post(self.checkout_url, self.checkout_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.client.session["cart"], {str(product_id): 1})
        self.assertEqual(response.url, reverse("store:cart"))

    def test_empty_cart_cannot_create_order(self):
        self.client.force_login(self.user)
        response = self.client.post(self.checkout_url, self.checkout_data)

        self.assertRedirects(response, reverse("store:cart"))
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_checkout_data_cannot_create_order(self):
        self.client.force_login(self.user)
        self.set_cart({str(self.product.pk): 1})
        invalid_data = self.checkout_data | {"email": "invalid"}

        response = self.client.post(self.checkout_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 1})

    def test_confirmation_requires_login_and_is_owner_only(self):
        response = self.place_order()
        order = Order.objects.get()
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("store:order_confirmation", args=[order.pk])).status_code,
            302,
        )
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse("store:order_confirmation", args=[order.pk])).status_code,
            404,
        )
        self.assertEqual(response.status_code, 302)

    def test_confirmation_refresh_does_not_create_duplicate_order(self):
        response = self.place_order()
        confirmation = self.client.get(response.url)

        self.assertEqual(confirmation.status_code, 200)
        self.client.get(response.url)
        self.assertEqual(Order.objects.count(), 1)

    def test_final_order_creation_requires_post(self):
        self.client.force_login(self.user)
        self.set_cart({str(self.product.pk): 1})

        response = self.client.get(self.checkout_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_transaction_rolls_back_order_and_stock_on_item_failure(self):
        self.client.force_login(self.user)
        self.set_cart({str(self.product.pk): 1})
        with patch("store.views.OrderItem.objects.create", side_effect=DatabaseError):
            response = self.client.post(self.checkout_url, self.checkout_data)

        self.assertRedirects(response, reverse("store:checkout"))
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 1})


class OrderHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="historyuser",
            password="StrongPassword123!",
            email="history@example.com",
        )
        self.other_user = User.objects.create_user(
            username="otherhistoryuser",
            password="StrongPassword123!",
        )
        self.product = Product.objects.create(
            name="Historical Product",
            description="A product for history tests.",
            price="75.00",
            category="General",
            stock=5,
            is_available=True,
        )
        self.history_url = reverse("store:order_history")

    def create_order(self, user=None, total="150.00", name="History Customer"):
        return Order.objects.create(
            user=user or self.user,
            full_name=name,
            email="customer@example.com",
            phone="03001234567",
            address="123 History Street",
            city="Karachi",
            state="Sindh",
            postal_code="74000",
            country="Pakistan",
            total_amount=total,
        )

    def create_order_item(self, order, product=None):
        return OrderItem.objects.create(
            order=order,
            product=product or self.product,
            product_name="Historical Product",
            price="75.00",
            quantity=2,
            subtotal="150.00",
        )

    def test_anonymous_users_are_redirected_from_history_and_detail(self):
        order = self.create_order()

        self.assertRedirects(
            self.client.get(self.history_url),
            f"{reverse('store:login')}?next={self.history_url}",
        )
        detail_url = reverse("store:order_detail", args=[order.pk])
        self.assertRedirects(
            self.client.get(detail_url),
            f"{reverse('store:login')}?next={detail_url}",
        )

    def test_history_uses_correct_template_and_only_shows_current_users_orders(self):
        own_order = self.create_order()
        other_order = self.create_order(user=self.other_user, name="Private Customer")
        self.client.force_login(self.user)

        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "store/order_history.html")
        self.assertContains(response, f"Order #{own_order.pk}")
        self.assertNotContains(response, f"Order #{other_order.pk}")
        self.assertNotContains(response, "Private Customer")

    def test_history_orders_are_newest_first(self):
        older = self.create_order(total="10.00")
        newer = self.create_order(total="20.00")
        Order.objects.filter(pk=older.pk).update(created_at="2026-09-17T12:00:00Z")
        Order.objects.filter(pk=newer.pk).update(created_at="2026-09-18T12:00:00Z")
        self.client.force_login(self.user)

        response = self.client.get(self.history_url)

        content = response.content.decode()
        self.assertLess(content.index(f"Order #{newer.pk}"), content.index(f"Order #{older.pk}"))

    def test_empty_history_shows_start_shopping_link(self):
        self.client.force_login(self.user)

        response = self.client.get(self.history_url)

        self.assertContains(response, "You have not placed any orders yet.")
        self.assertContains(response, f'href="{reverse("store:product_list")}"')
        self.assertContains(response, "Start Shopping")

    def test_user_can_view_own_order_details(self):
        order = self.create_order()
        self.create_order_item(order)
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:order_detail", args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "store/order_detail.html")
        self.assertContains(response, "Order Information")
        self.assertContains(response, "History Customer")
        self.assertContains(response, "customer@example.com")
        self.assertContains(response, "123 History Street")
        self.assertContains(response, "Pending")
        self.assertContains(response, "Historical Product")
        self.assertContains(response, "75.00")
        self.assertContains(response, "150.00")
        self.assertContains(response, "2")

    def test_user_cannot_view_another_users_order_details(self):
        order = self.create_order(user=self.other_user, name="Private Customer")
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:order_detail", args=[order.pk]))

        self.assertEqual(response.status_code, 404)

    def test_order_detail_uses_historical_name_and_price_after_product_changes(self):
        order = self.create_order()
        self.create_order_item(order)
        self.product.name = "Current Product Name"
        self.product.price = "999.99"
        self.product.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:order_detail", args=[order.pk]))

        self.assertContains(response, "Historical Product")
        self.assertContains(response, "75.00")
        self.assertNotContains(response, "Current Product Name")
        self.assertNotContains(response, "999.99")

    def test_order_detail_survives_deleted_product(self):
        order = self.create_order()
        self.create_order_item(order)
        self.product.delete()
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:order_detail", args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Historical Product")
        self.assertContains(response, "Product image unavailable")
        self.assertContains(response, "75.00")
        self.assertContains(response, "150.00")

    def test_authenticated_navigation_shows_my_orders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:home"))

        self.assertContains(response, f'href="{self.history_url}"')
        self.assertContains(response, "My Orders")

    def test_anonymous_navigation_hides_my_orders(self):
        response = self.client.get(reverse("store:home"))

        self.assertNotContains(response, "My Orders")

    def test_confirmation_links_to_history_and_detail(self):
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:order_confirmation", args=[order.pk]))

        self.assertContains(response, reverse("store:order_history"))
        self.assertContains(response, reverse("store:order_detail", args=[order.pk]))


class SecurityAndErrorHandlingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="securityuser",
            password="StrongPassword123!",
            email="security@example.com",
        )
        self.other_user = User.objects.create_user(
            username="securityother",
            password="StrongPassword123!",
        )
        self.product = Product.objects.create(
            name="Secure Product",
            description="A product for security tests.",
            price="25.00",
            category="General",
            stock=3,
            is_available=True,
        )
        self.checkout_data = {
            "full_name": "Security Customer",
            "email": "customer@example.com",
            "phone": "03001234567",
            "address": "123 Secure Street",
            "city": "Karachi",
            "state": "Sindh",
            "postal_code": "74000",
            "country": "Pakistan",
            "review_only": "1",
        }

    def set_cart(self, client, cart=None):
        session = client.session
        session["cart"] = cart or {str(self.product.pk): 1}
        session.save()

    def test_anonymous_users_cannot_access_private_routes(self):
        private_urls = [
            reverse("store:cart"),
            reverse("store:checkout"),
            reverse("store:order_history"),
        ]

        for url in private_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("store:login"), response.url)

    def test_anonymous_users_cannot_change_cart_or_place_order(self):
        add_url = reverse("store:add_to_cart", args=[self.product.pk])
        checkout_url = reverse("store:checkout")

        self.assertEqual(self.client.post(add_url).status_code, 302)
        self.assertEqual(self.client.post(checkout_url, self.checkout_data).status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_get_cannot_change_cart_or_create_order(self):
        self.client.force_login(self.user)
        self.set_cart(self.client)
        add_url = reverse("store:add_to_cart", args=[self.product.pk])
        original_cart = self.client.session["cart"].copy()

        self.assertEqual(self.client.get(add_url).status_code, 405)
        self.assertEqual(self.client.get(reverse("store:checkout")).status_code, 200)
        self.assertEqual(self.client.session["cart"], original_cart)
        self.assertEqual(Order.objects.count(), 0)

    def test_csrf_rejects_state_changing_cart_and_order_posts(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.set_cart(csrf_client)

        add_response = csrf_client.post(reverse("store:add_to_cart", args=[self.product.pk]))
        order_response = csrf_client.post(reverse("store:checkout"), self.checkout_data)

        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(order_response.status_code, 403)
        self.assertEqual(Order.objects.count(), 0)

    def test_negative_zero_and_non_numeric_cart_quantities_are_rejected(self):
        self.client.force_login(self.user)
        update_url = reverse("store:update_cart", args=[self.product.pk])

        for quantity in ("-1", "0", "abc"):
            with self.subTest(quantity=quantity):
                self.set_cart(self.client, {str(self.product.pk): 1})
                response = self.client.post(update_url, {"quantity": quantity})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.client.session["cart"], {str(self.product.pk): 1})

    def test_excessive_quantity_does_not_reduce_stock_or_create_order(self):
        self.client.force_login(self.user)
        self.set_cart(self.client, {str(self.product.pk): 99})

        response = self.client.post(reverse("store:checkout"), self.checkout_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_invalid_product_id_is_handled_without_server_error(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("store:add_to_cart", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_unavailable_product_cannot_be_added_or_ordered(self):
        self.product.is_available = False
        self.product.save()
        self.client.force_login(self.user)

        add_response = self.client.post(reverse("store:add_to_cart", args=[self.product.pk]))
        self.set_cart(self.client)
        order_response = self.client.post(reverse("store:checkout"), self.checkout_data)

        self.assertEqual(add_response.status_code, 302)
        self.assertEqual(order_response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_fake_submitted_total_does_not_change_server_calculated_order_total(self):
        self.client.force_login(self.user)
        self.set_cart(self.client, {str(self.product.pk): 2})
        fake_total_data = self.checkout_data | {"total": "0.01", "price": "0.01"}

        response = self.client.post(reverse("store:checkout"), fake_total_data)

        order = Order.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.total_amount, Decimal("50.00"))

    def test_invalid_filter_input_and_sort_are_safe(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("store:product_list"),
            {"min_price": "not-a-price", "max_price": "-5", "sort": "-created_at"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a valid minimum price.")
        self.assertContains(response, "Please enter a valid maximum price.")
        self.assertEqual(response.context["filters"]["sort"], "newest")

    def test_order_detail_denies_another_users_order(self):
        order = Order.objects.create(
            user=self.other_user,
            full_name="Private Customer",
            email="private@example.com",
            phone="03000000000",
            address="Private Address",
            city="Karachi",
            state="Sindh",
            postal_code="74000",
            country="Pakistan",
            total_amount="25.00",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("store:order_detail", args=[order.pk]))

        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    def test_custom_404_page_is_rendered_without_debug_details(self):
        response = self.client.get("/security-missing-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page not found.", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_custom_500_page_is_rendered_without_internal_details(self):
        request = RequestFactory().get("/error/")
        request.session = self.client.session
        request.user = AnonymousUser()

        response = custom_500(request)

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Something went wrong.", status_code=500)
        self.assertNotContains(response, "SECRET_KEY", status_code=500)

    def test_security_defaults_are_safe_for_local_development(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertFalse(settings.SECURE_SSL_REDIRECT)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

