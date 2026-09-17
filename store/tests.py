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
