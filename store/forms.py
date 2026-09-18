from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"placeholder": "Enter your username"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}),
    )


class CheckoutForm(forms.Form):
    full_name = forms.CharField(label="Full name", max_length=200)
    email = forms.EmailField(label="Email address")
    phone = forms.CharField(label="Phone number", max_length=30)
    address = forms.CharField(label="Street address", max_length=255)
    city = forms.CharField(label="City", max_length=100)
    state = forms.CharField(label="State/Province", max_length=100)
    postal_code = forms.CharField(label="Postal code", max_length=20)
    country = forms.CharField(label="Country", max_length=100)