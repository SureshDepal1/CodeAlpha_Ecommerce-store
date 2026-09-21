from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from . import forms, views


class StorePasswordResetView(auth_views.PasswordResetView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class StorePasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    post_reset_login = False


app_name = "store"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:product_id>/", views.update_cart, name="update_cart"),
    path("cart/increase/<int:product_id>/", views.increase_cart_quantity, name="increase_cart_quantity"),
    path("cart/decrease/<int:product_id>/", views.decrease_cart_quantity, name="decrease_cart_quantity"),
    path("cart/remove/<int:product_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/", views.cart_view, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.order_history, name="order_history"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/confirmation/", views.order_confirmation, name="order_confirmation"),
    path("register/", views.register, name="register"),
    path("verify/", views.verify_email, name="verify_email"),
    path("login/", views.login_view, name="login"),
    path(
        "password-reset/",
        StorePasswordResetView.as_view(
            form_class=forms.StorePasswordResetForm,
            template_name="store/password_reset_form.html",
            email_template_name="emails/password_reset.txt",
            html_email_template_name="emails/password_reset.html",
            subject_template_name="emails/password_reset_subject.txt",
            success_url=reverse_lazy("store:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="store/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        StorePasswordResetConfirmView.as_view(
            template_name="store/password_reset_confirm.html",
            success_url=reverse_lazy("store:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="store/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("logout/", views.logout_view, name="logout"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("contact/", views.contact, name="contact"),
]
