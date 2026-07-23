from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone


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
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; "
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
                request.session[LAST_ACTIVITY_KEY] = now_timestamp

        response = self.get_response(request)

        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            request.session[LAST_ACTIVITY_KEY] = int(timezone.now().timestamp())

        return response
