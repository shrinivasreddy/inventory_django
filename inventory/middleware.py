from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import hashlib
import time


class AuthenticationRateLimitMiddleware(MiddlewareMixin):
    """Bound authentication POST traffic in the supported single-process deployment."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if request.method != 'POST' or not match or match.url_name not in {'login', 'password_reset', 'signup'}:
            return None
        window = 300
        now = int(time.time())
        bucket = now // window
        # Never trust a client-supplied forwarded IP header.
        address = request.META.get('REMOTE_ADDR', '')
        identity = request.POST.get('username') or request.POST.get('email') or ''
        checks = [(address, 100), (address + ':' + identity.strip().casefold(), 15)]
        for value, limit in checks:
            digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
            key = f'auth-rate:{match.url_name}:{bucket}:{digest}'
            if cache.add(key, 1, timeout=window + 1):
                count = 1
            else:
                try:
                    count = cache.incr(key)
                except ValueError:
                    cache.add(key, 1, timeout=window + 1)
                    count = 1
            if count > limit:
                response = HttpResponse('Too many attempts. Please wait a few minutes and try again.', status=429, content_type='text/plain')
                response['Retry-After'] = str(window - now % window)
                response['Cache-Control'] = 'no-store'
                return response
        return None


LAST_ACTIVITY_KEY = "_inventory_last_activity"
LEGACY_EXPIRY_TOLERANCE_SECONDS = 60


class SecurityHeadersMiddleware:
    """Add browser hardening and prevent caching of authenticated pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: "
            + " ".join(settings.INVENTORY_IMAGE_ORIGINS) + "; "
            +
            "connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
        response.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=(self), payment=(), usb=()",
        )
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
        return response


class SessionExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        now_timestamp = int(timezone.now().timestamp())
        if request.user.is_authenticated:
            last_activity = request.session.get(LAST_ACTIVITY_KEY)
            session_age = settings.SESSION_COOKIE_AGE
            is_expired = False

            if last_activity is None:
                is_expired = (
                    request.session.get_expiry_age()
                    > session_age + LEGACY_EXPIRY_TOLERANCE_SECONDS
                )
            else:
                try:
                    is_expired = now_timestamp - int(last_activity) > session_age
                except (TypeError, ValueError):
                    is_expired = True

            if is_expired:
                request.session.flush()
                request.user = AnonymousUser()
            else:
                # Avoid a database session write for every API request. A
                # once-per-minute refresh preserves inactivity semantics while
                # allowing concurrent read traffic to remain read-only.
                try:
                    activity_age = now_timestamp - int(last_activity or 0)
                except (TypeError, ValueError):
                    activity_age = settings.SESSION_ACTIVITY_UPDATE_INTERVAL
                if activity_age >= settings.SESSION_ACTIVITY_UPDATE_INTERVAL:
                    request.session[LAST_ACTIVITY_KEY] = now_timestamp

        response = self.get_response(request)

        return response
