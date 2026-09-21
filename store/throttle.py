import hashlib
import logging
import math
import time

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


def _login_state(key):
    state = cache.get(key)
    if not isinstance(state, dict):
        return {"count": 0, "blocked_until": 0}
    return state


def login_blocked(request, username, user_limit, ip_limit, lockout_seconds):
    try:
        now = time.time()
        states = (_login_state(login_counter_key(username, request)), _login_state(login_ip_key(request)))
        blocked_until = max(state["blocked_until"] for state in states)
        if blocked_until > now:
            return True, max(1, math.ceil((blocked_until - now) / 60))
        return False, 0
    except Exception:
        logger.warning("Login throttle cache unavailable; allowing request.", exc_info=True)
        return False, 0


def record_login_failure(request, username, user_limit, ip_limit, lockout_seconds):
    try:
        now = time.time()
        for key, limit in (
            (login_counter_key(username, request), user_limit),
            (login_ip_key(request), ip_limit),
        ):
            state = _login_state(key)
            state["count"] += 1
            if state["count"] >= limit:
                state["blocked_until"] = now + lockout_seconds
            cache.set(key, state, lockout_seconds)
    except Exception:
        logger.warning("Login throttle cache unavailable; allowing request.", exc_info=True)


def reset_login_user(request, username):
    reset(login_counter_key(username, request))