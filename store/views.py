import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Count, Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.http import require_POST

from .forms import CheckoutForm, LoginForm, RegistrationForm
from .emails import send_order_emails, send_verification_code
from .models import EmailVerification, Order, OrderItem, Product
from .throttle import (
    login_blocked,
    record_login_failure,
    registration_throttled,
    reset_login_user,
    throttle_key,
)


PENDING_VERIFICATION_SESSION_KEY = "pending_verification_user_id"


def _pending_users():
    return User.objects.filter(
        is_active=False,
        email_verification__isnull=False,
        email_verification__verified_at__isnull=True,
    )


def _purge_expired_unverified_users(minutes=None):
    lifetime = minutes if minutes is not None else settings.UNVERIFIED_ACCOUNT_LIFETIME_MINUTES
    cutoff = timezone.now() - timedelta(minutes=lifetime)
    users = _pending_users().filter(
        email_verification__created_at__lt=cutoff,
        orders__isnull=True,
        is_staff=False,
        is_superuser=False,
    ).distinct()
    count, _ = users.delete()
    return count


def _new_verification_code():
    return f"{secrets.randbelow(10 ** settings.OTP_LENGTH):0{settings.OTP_LENGTH}d}"


def _verification_hash(user, code):
    return salted_hmac(
        "email-verification",
        code,
        secret=f"{settings.SECRET_KEY}:{user.pk}",
    ).hexdigest()


def _mask_email(email):
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def _throttle_key(prefix, value):
    return throttle_key(prefix, value)


def _registration_throttled(request, email):
    return registration_throttled(
        request,
        email,
        settings.OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR,
        settings.OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR,
    )


def _send_new_verification_code(user, verification):
    now = timezone.now()
    if verification.code_sent_at + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS) > now:
        return "cooldown"
    if verification.send_count >= settings.OTP_MAX_SENDS:
        return "max"

    code = _new_verification_code()
    send_verification_code(user, code)
    verification.code_hash = _verification_hash(user, code)
    verification.code_sent_at = now
    verification.expires_at = now + timedelta(seconds=settings.OTP_EXPIRY_SECONDS)
    verification.attempts = 0
    verification.send_count += 1
    verification.save(update_fields=("code_hash", "code_sent_at", "expires_at", "attempts", "send_count"))
    return "sent"


def _create_order_from_cart(user, form, session):
    cart = session.get("cart", {})
    if not cart:
        raise ValueError("Your cart is empty.")

    product_ids = []
    quantities = {}
    for raw_product_id, raw_quantity in cart.items():
        try:
            product_id = int(raw_product_id)
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            raise ValueError("Your cart contains invalid items.")
        if quantity <= 0:
            raise ValueError("Cart quantities must be greater than zero.")
        product_ids.append(product_id)
        quantities[product_id] = quantity

    with transaction.atomic():
        products = Product.objects.select_for_update().filter(pk__in=product_ids)
        products_by_id = {product.pk: product for product in products}
        if len(products_by_id) != len(product_ids):
            raise ValueError("One or more products in your cart no longer exist.")

        items = []
        total = Decimal("0.00")
        for product_id in product_ids:
            product = products_by_id[product_id]
            quantity = quantities[product_id]
            if not product.is_available or product.stock <= 0:
                raise ValueError(f"{product.name} is no longer available.")
            if quantity > product.stock:
                raise ValueError(f"Only {product.stock} of {product.name} are available.")
            subtotal = product.price * quantity
            total += subtotal
            items.append((product, quantity, subtotal))

        order = Order.objects.create(
            user=user,
            full_name=form.cleaned_data["full_name"],
            email=form.cleaned_data["email"],
            phone=form.cleaned_data["phone"],
            address=form.cleaned_data["address"],
            city=form.cleaned_data["city"],
            state=form.cleaned_data["state"],
            postal_code=form.cleaned_data["postal_code"],
            country=form.cleaned_data["country"],
            total_amount=total,
        )
        for product, quantity, subtotal in items:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                price=product.price,
                quantity=quantity,
                subtotal=subtotal,
            )
            product.stock -= quantity
            if product.stock == 0:
                product.is_available = False
            product.save(update_fields=("stock", "is_available", "updated_at"))

    session["cart"] = {}
    session.modified = True
    return order


def _get_checkout_cart_summary(request):
    cart = _normalize_cart(request.session)
    if not cart:
        return None

    cart_items = []
    total = Decimal("0.00")
    cleaned_cart = {}
    has_forbidden_item = False

    for raw_product_id, quantity in cart.items():
        try:
            product_id = int(raw_product_id)
        except (TypeError, ValueError):
            continue

        try:
            item_quantity = int(quantity)
        except (TypeError, ValueError):
            continue

        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            continue

        if not product.is_available or product.stock <= 0:
            has_forbidden_item = True
            continue

        if item_quantity > product.stock:
            has_forbidden_item = True
            continue

        final_quantity = item_quantity
        if final_quantity <= 0:
            continue

        cleaned_cart[str(product.id)] = final_quantity

        subtotal = product.price * final_quantity
        cart_items.append(
            {
                "product": product,
                "quantity": final_quantity,
                "subtotal": subtotal,
            }
        )
        total += subtotal

    request.session["cart"] = cleaned_cart
    request.session.modified = True

    if not cart_items:
        return None

    return {"cart_items": cart_items, "total": total, "invalid": has_forbidden_item}


def _normalize_cart(session):
    cart = session.get("cart", {})
    cleaned = {}
    changed = False

    for raw_product_id, quantity in cart.items():
        try:
            product_id = str(int(raw_product_id))
        except (TypeError, ValueError):
            changed = True
            continue

        try:
            quantity_value = int(quantity)
        except (TypeError, ValueError):
            changed = True
            continue

        if quantity_value <= 0:
            changed = True
            continue

        cleaned[product_id] = quantity_value

    if changed:
        session["cart"] = cleaned
        session.modified = True

    return cleaned


def home(request):
    featured_products = Product.objects.filter(is_available=True).order_by("-created_at")[:4]
    return render(request, "store/home.html", {"featured_products": featured_products})


def custom_404(request, exception):
    return render(request, "404.html", status=404)


def custom_500(request):
    return render(request, "500.html", status=500)


def privacy(request):
    return render(request, "store/privacy.html")


def terms(request):
    return render(request, "store/terms.html")


def contact(request):
    return render(request, "store/contact.html")


def product_list(request):
    query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    availability = request.GET.get("availability", "all").strip()
    selected_sort = request.GET.get("sort", "newest").strip()
    min_price_input = request.GET.get("min_price", "").strip()
    max_price_input = request.GET.get("max_price", "").strip()

    products = Product.objects.filter(is_available=True)
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__icontains=query)
        )
    if selected_category:
        products = products.filter(category__iexact=selected_category)

    if availability == "in_stock":
        products = products.filter(stock__gt=0)
    elif availability == "out_of_stock":
        products = products.filter(stock=0)
    else:
        availability = "all"

    min_price = _parse_filter_price(min_price_input, "minimum", request)
    max_price = _parse_filter_price(max_price_input, "maximum", request)
    if min_price is not None:
        products = products.filter(price__gte=min_price)
    if max_price is not None:
        products = products.filter(price__lte=max_price)
    if min_price is not None and max_price is not None and min_price > max_price:
        messages.error(request, "Minimum price cannot be greater than maximum price.")
        products = products.none()

    sort_options = {
        "newest": "-created_at",
        "price_low": "price",
        "price_high": "-price",
        "name_az": "name",
        "name_za": "-name",
    }
    if selected_sort not in sort_options:
        selected_sort = "newest"
    products = products.order_by(sort_options[selected_sort])
    result_count = products.count()
    paginator = Paginator(products, 24)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_query = request.GET.copy()
    filter_query.pop("page", None)

    category_labels = {}
    for category in Product.objects.filter(is_available=True).values_list("category", flat=True):
        if category and category.strip():
            category_label = category.strip()
            category_labels.setdefault(category_label.casefold(), category_label)
    categories = sorted(category_labels.values(), key=str.casefold)
    return render(
        request,
        "store/product_list.html",
        {
            "products": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "filter_query": filter_query.urlencode(),
            "result_count": result_count,
            "categories": categories,
            "filters": {
                "q": query,
                "category": selected_category,
                "availability": availability,
                "min_price": min_price_input,
                "max_price": max_price_input,
                "sort": selected_sort,
            },
        },
    )


def _parse_filter_price(value, label, request):
    if not value:
        return None
    try:
        parsed_value = Decimal(value)
    except (TypeError, ValueError, InvalidOperation):
        messages.error(request, f"Please enter a valid {label} price.")
        return None
    if not parsed_value.is_finite() or parsed_value < 0 or parsed_value > Decimal("99999999.99"):
        messages.error(request, f"Please enter a valid {label} price.")
        return None
    return parsed_value


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_available=True)
    return render(request, "store/product_detail.html", {"product": product})


@login_required(login_url="store:login")
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if not product.is_available:
        messages.error(request, "Product is unavailable.")
        return redirect("store:cart")

    if product.stock <= 0:
        messages.error(request, "Product is out of stock.")
        return redirect("store:cart")

    cart = _normalize_cart(request.session)
    current_quantity = int(cart.get(str(product.id), 0))
    next_quantity = current_quantity + 1

    if next_quantity > product.stock:
        messages.error(request, "Maximum available stock has been reached.")
        return redirect("store:cart")

    cart[str(product.id)] = next_quantity
    request.session["cart"] = cart
    request.session.modified = True
    messages.success(request, "Product added to cart.")
    return redirect("store:cart")


@login_required(login_url="store:login")
def cart_view(request):
    cart = _normalize_cart(request.session)
    cart_items = []
    total = Decimal("0.00")

    if cart:
        cleaned_cart = {}

        for raw_product_id, quantity in cart.items():
            try:
                product_id = int(raw_product_id)
            except (TypeError, ValueError):
                continue

            try:
                item_quantity = int(quantity)
            except (TypeError, ValueError):
                continue

            product = Product.objects.filter(pk=product_id).first()

            if product is None:
                continue

            if not product.is_available or product.stock <= 0:
                continue

            item_quantity = min(item_quantity, product.stock)
            cleaned_cart[str(product.id)] = item_quantity

            subtotal = product.price * item_quantity
            cart_items.append(
                {
                    "product": product,
                    "quantity": item_quantity,
                    "subtotal": subtotal,
                }
            )
            total += subtotal

        request.session["cart"] = cleaned_cart
        request.session.modified = True

    if not cart_items:
        request.session["cart"] = {}
        request.session.modified = True

    return render(
        request,
        "store/cart.html",
        {
            "cart_items": cart_items,
            "total": total,
            "cart_count": sum(item["quantity"] for item in cart_items),
        },
    )


@login_required(login_url="store:login")
@require_POST
def update_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart = _normalize_cart(request.session)
    current_quantity = int(cart.get(str(product_id), 0))
    raw_quantity = request.POST.get("quantity")

    if not product.is_available:
        messages.error(request, "Product is unavailable.")
        if str(product_id) in cart:
            cart.pop(str(product_id))
            request.session["cart"] = cart
            request.session.modified = True
        return redirect("store:cart")

    if product.stock <= 0:
        messages.error(request, "Product is out of stock.")
        cart.pop(str(product_id), None)
        request.session["cart"] = cart
        request.session.modified = True
        return redirect("store:cart")

    try:
        quantity = int(raw_quantity)
    except (TypeError, ValueError):
        messages.error(request, "Please enter a valid quantity.")
        return redirect("store:cart")

    if quantity <= 0:
        messages.error(request, "Please enter a valid quantity.")
        return redirect("store:cart")

    if quantity > product.stock:
        quantity = product.stock
        messages.info(request, f"Only {product.stock} items are available.")

    cart[str(product_id)] = quantity
    request.session["cart"] = cart
    request.session.modified = True
    messages.success(request, "Cart updated.")
    return redirect("store:cart")


@login_required(login_url="store:login")
@require_POST
def increase_cart_quantity(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart = _normalize_cart(request.session)

    if not product.is_available:
        messages.error(request, "Product is unavailable.")
        cart.pop(str(product_id), None)
        request.session["cart"] = cart
        request.session.modified = True
        return redirect("store:cart")

    if product.stock <= 0:
        messages.error(request, "Product is out of stock.")
        cart.pop(str(product_id), None)
        request.session["cart"] = cart
        request.session.modified = True
        return redirect("store:cart")

    current_quantity = int(cart.get(str(product_id), 0))
    if current_quantity >= product.stock:
        messages.error(request, "Maximum available stock reached.")
        return redirect("store:cart")

    cart[str(product_id)] = current_quantity + 1
    request.session["cart"] = cart
    request.session.modified = True
    messages.success(request, "Quantity increased.")
    return redirect("store:cart")


@login_required(login_url="store:login")
@require_POST
def decrease_cart_quantity(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart = _normalize_cart(request.session)

    if not product.is_available:
        messages.error(request, "Product is unavailable.")
        cart.pop(str(product_id), None)
        request.session["cart"] = cart
        request.session.modified = True
        return redirect("store:cart")

    if str(product_id) not in cart:
        return redirect("store:cart")

    current_quantity = int(cart.get(str(product_id), 0))

    if current_quantity <= 1:
        cart.pop(str(product_id), None)
        messages.info(request, "Item removed from cart.")
    else:
        cart[str(product_id)] = current_quantity - 1
        messages.info(request, "Quantity decreased.")

    request.session["cart"] = cart
    request.session.modified = True
    return redirect("store:cart")


@login_required(login_url="store:login")
@require_POST
def remove_from_cart(request, product_id):
    cart = _normalize_cart(request.session)

    if str(product_id) in cart:
        cart.pop(str(product_id), None)
        request.session["cart"] = cart
        request.session.modified = True
        messages.info(request, "Item removed from cart.")

    return redirect("store:cart")


def register(request):
    if request.user.is_authenticated:
        return redirect("store:home")

    _purge_expired_unverified_users()
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            if _registration_throttled(request, email):
                form.add_error(None, "Too many attempts, please try again later.")
            else:
                try:
                    with transaction.atomic():
                        user = form.save(commit=False)
                        user.email = email
                        user.is_active = False
                        user.save()
                        code = _new_verification_code()
                        now = timezone.now()
                        verification = EmailVerification.objects.create(
                            user=user,
                            code_hash=_verification_hash(user, code),
                            code_sent_at=now,
                            expires_at=now + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
                        )
                        send_verification_code(user, code)
                except Exception:
                    form.add_error(None, "We couldn't send the verification email. Please check the address and try again.")
                else:
                    request.session[PENDING_VERIFICATION_SESSION_KEY] = user.pk
                    return redirect("store:verify_email")
    else:
        form = RegistrationForm()

    return render(request, "store/register.html", {"form": form})


def verify_email(request):
    user_id = request.session.get(PENDING_VERIFICATION_SESSION_KEY)
    user = _pending_users().filter(pk=user_id).select_related("email_verification").first()
    if user is None:
        messages.info(request, "Please start registration again to verify your email.")
        return redirect("store:register")

    verification = user.email_verification
    if request.method == "POST":
        action = request.POST.get("action", "verify")
        if action == "resend":
            try:
                result = _send_new_verification_code(user, verification)
            except Exception:
                messages.error(request, "We couldn't send the verification email. Please try again later.")
            else:
                if result == "sent":
                    messages.success(request, "A new code has been sent.")
                elif result == "cooldown":
                    messages.error(request, "Please wait before requesting another code.")
                else:
                    messages.error(request, "You have reached the resend limit. Please register again.")
            return redirect("store:verify_email")

        code = request.POST.get("code", "").strip()
        if not code.isdigit() or len(code) != settings.OTP_LENGTH:
            messages.error(request, f"Enter the {settings.OTP_LENGTH}-digit code.")
        elif verification.expires_at <= timezone.now():
            messages.error(request, "This code has expired. Request a new one.")
        elif verification.attempts >= settings.OTP_MAX_ATTEMPTS:
            messages.error(request, "Too many incorrect attempts. Request a new code.")
        elif not constant_time_compare(verification.code_hash, _verification_hash(user, code)):
            verification.attempts += 1
            verification.save(update_fields=("attempts",))
            remaining = settings.OTP_MAX_ATTEMPTS - verification.attempts
            if remaining <= 0:
                messages.error(request, "Too many incorrect attempts. Request a new code.")
            else:
                messages.error(request, f"Incorrect code. {remaining} attempts left.")
        else:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=user.pk)
                verification = EmailVerification.objects.select_for_update().get(user=user)
                User.objects.filter(
                    email__iexact=user.email,
                    is_active=False,
                    email_verification__isnull=False,
                    email_verification__verified_at__isnull=True,
                ).exclude(pk=user.pk).delete()
                user.is_active = True
                user.save(update_fields=("is_active",))
                verification.verified_at = timezone.now()
                verification.code_hash = ""
                verification.save(update_fields=("verified_at", "code_hash"))
            request.session.pop(PENDING_VERIFICATION_SESSION_KEY, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Account created successfully.")
            return redirect("store:home")

    now = timezone.now()
    resend_at = verification.code_sent_at + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    seconds_until_resend = max(0, int((resend_at - now).total_seconds()))
    return render(
        request,
        "store/verify_email.html",
        {
            "masked_email": _mask_email(user.email),
            "seconds_until_resend": seconds_until_resend,
            "dev_console_hint": settings.DEBUG and settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend",
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("store:home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        blocked, minutes = login_blocked(
            request,
            username,
            settings.LOGIN_MAX_FAILED_PER_USER_IP,
            settings.LOGIN_MAX_FAILED_PER_IP,
            settings.LOGIN_LOCKOUT_SECONDS,
        )
        if blocked:
            form = LoginForm(request=request, data=request.POST)
            form.add_error(None, f"Too many login attempts. Please try again in {minutes} minutes.")
            return render(request, "store/login.html", {"form": form}, status=429)
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            reset_login_user(request, username)
            login(request, form.get_user())
            return redirect("store:home")
        password = request.POST.get("password", "")
        pending_user = _pending_users().filter(username=username).select_related("email_verification").first()
        if pending_user and check_password(password, pending_user.password):
            reset_login_user(request, username)
            request.session[PENDING_VERIFICATION_SESSION_KEY] = pending_user.pk
            try:
                result = _send_new_verification_code(pending_user, pending_user.email_verification)
            except Exception:
                messages.error(request, "We couldn't send the verification email. Please try again later.")
            else:
                if result == "sent":
                    messages.info(request, "A new verification code has been sent.")
                elif result == "cooldown":
                    messages.info(request, "Your verification code is still valid. Please check your email.")
                else:
                    messages.error(request, "You have reached the resend limit. Please register again.")
            return redirect("store:verify_email")
        record_login_failure(
            request,
            username,
            settings.LOGIN_MAX_FAILED_PER_USER_IP,
            settings.LOGIN_MAX_FAILED_PER_IP,
            settings.LOGIN_LOCKOUT_SECONDS,
        )
    else:
        form = LoginForm(request=request)

    return render(request, "store/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("store:home")


@login_required(login_url="store:login")
def checkout(request):
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            if request.POST.get("review_only") == "1":
                original_cart = request.session.get("cart", {}).copy()
                try:
                    order = _create_order_from_cart(request.user, form, request.session)
                except ValueError as error:
                    request.session["cart"] = original_cart
                    request.session.modified = True
                    messages.error(request, str(error))
                    return redirect("store:cart")
                except DatabaseError:
                    request.session["cart"] = original_cart
                    request.session.modified = True
                    messages.error(request, "We could not place your order. Please try again.")
                    return redirect("store:checkout")
                transaction.on_commit(lambda: send_order_emails(order))
                messages.success(request, "Your order has been placed successfully.")
                return redirect("store:order_confirmation", pk=order.pk)

            cart_summary = _get_checkout_cart_summary(request)
            if cart_summary is None:
                messages.info(request, "Your cart is empty.")
                return redirect("store:cart")
            if cart_summary["invalid"]:
                messages.error(request, "One or more items in your cart are no longer available in the requested quantity.")
                return redirect("store:cart")
            return render(
                request,
                "store/checkout.html",
                {
                    "form": form,
                    "cart_items": cart_summary["cart_items"],
                    "total": cart_summary["total"],
                    "review_only": True,
                },
            )

        cart_summary = _get_checkout_cart_summary(request)
        if cart_summary is None:
            messages.info(request, "Your cart is empty.")
            return redirect("store:cart")

        return render(
            request,
            "store/checkout.html",
            {
                "form": form,
                "cart_items": cart_summary["cart_items"],
                "total": cart_summary["total"],
            },
        )

    cart_summary = _get_checkout_cart_summary(request)
    if cart_summary is None:
        messages.info(request, "Your cart is empty.")
        return redirect("store:cart")
    if cart_summary["invalid"]:
        messages.error(request, "One or more items in your cart are no longer available in the requested quantity.")
        return redirect("store:cart")

    form = CheckoutForm(initial={"email": request.user.email or ""})
    return render(
        request,
        "store/checkout.html",
        {
            "form": form,
            "cart_items": cart_summary["cart_items"],
            "total": cart_summary["total"],
        },
    )


@login_required(login_url="store:login")
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .annotate(item_count=Count("items"))
        .order_by("-created_at")
    )
    return render(request, "store/order_history.html", {"orders": orders})


@login_required(login_url="store:login")
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=pk,
        user=request.user,
    )
    return render(request, "store/order_detail.html", {"order": order})


@login_required(login_url="store:login")
def order_confirmation(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        pk=pk,
        user=request.user,
    )
    return render(request, "store/order_confirmation.html", {"order": order})
