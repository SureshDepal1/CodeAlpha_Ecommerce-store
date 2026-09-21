import hashlib
import logging

from django.core.cache import cache


logger = logging.getLogger("store")


def throttle_key(prefix, value):
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return f"store-throttle:{prefix}:{digest}"


def increment_and_check(key, limit, timeout):
    try:
        if cache.add(key, 1, timeout):
            return False
        count = cache.incr(key)
        return count > limit
    except Exception:
        logger.warning("Throttle cache unavailable; allowing request.", exc_info=True)
        return False


def reset(key):
    try:
        cache.delete(key)
    except Exception:
        logger.warning("Throttle cache unavailable; could not reset counter.", exc_info=True)


def request_ip(request):
    return request.META.get("REMOTE_ADDR", "unknown")


def registration_throttled(request, email, email_limit, ip_limit, timeout=3600):
    return increment_and_check(throttle_key("registration-email", email), email_limit, timeout) or increment_and_check(
        throttle_key("registration-ip", request_ip(request)), ip_limit, timeout
    )


def password_reset_throttled(request, email, email_limit=3, ip_limit=5, timeout=3600):
    return increment_and_check(throttle_key("password-reset-email", email), email_limit, timeout) or increment_and_check(
        throttle_key("password-reset-ip", request_ip(request)), ip_limit, timeout
    )


def login_counter_key(username, request):
    return throttle_key("login-user-ip", f"{username.casefold()}:{request_ip(request)}")


def login_ip_key(request):
    return throttle_key("login-ip", request_ip(request))