from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username", "placeholder": "Choose a username"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({
            "autocomplete": "new-password",
            "placeholder": "Create a password",
        })
        self.fields["password2"].widget.attrs.update({
            "autocomplete": "new-password",
            "placeholder": "Confirm your password",
        })

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing_users = User.objects.filter(email__iexact=email).filter(
            Q(email_verification__isnull=True) | Q(email_verification__verified_at__isnull=False)
        )
        if existing_users.exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": "Enter your username"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Enter your password"}),
    )


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        label="Full name",
        max_length=200,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Your full name"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
    )
    phone = forms.CharField(
        label="Phone number",
        max_length=30,
        widget=forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "(555) 123-4567"}),
    )
    address = forms.CharField(
        label="Street address",
        max_length=255,
        widget=forms.TextInput(attrs={"autocomplete": "street-address", "placeholder": "Street address"}),
    )
    city = forms.CharField(
        label="City",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "address-level2", "placeholder": "City"}),
    )
    state = forms.CharField(
        label="State/Province",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "address-level1", "placeholder": "State or province"}),
    )
    postal_code = forms.CharField(
        label="Postal code",
        max_length=20,
        widget=forms.TextInput(attrs={"autocomplete": "postal-code", "placeholder": "Postal code"}),
    )
    country = forms.CharField(
        label="Country",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "country-name", "placeholder": "Country"}),
    )