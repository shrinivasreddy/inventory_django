from django.apps import AppConfig
from django.core.checks import Warning, register
from django.conf import settings


@register("security", deploy=True)
def password_reset_email_backend_check(app_configs, **kwargs):
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        return [
            Warning(
                "Account and password-reset notifications are using the console "
                "backend and will not be delivered to users.",
                hint=(
                    "Configure DJANGO_EMAIL_BACKEND and the DJANGO_EMAIL_* SMTP "
                    "settings documented in .env.example."
                ),
                id="inventory.W001",
            )
        ]
    if settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
        host = (settings.EMAIL_HOST or "").strip().lower()
        username = (settings.EMAIL_HOST_USER or "").strip().lower()
        if host == "smtp.example.com" or host.endswith(".example.com"):
            return [
                Warning(
                    "The SMTP host is an example placeholder, so emails cannot be delivered.",
                    hint="Set DJANGO_EMAIL_HOST to the real SMTP server in .env.",
                    id="inventory.W002",
                )
            ]
        if username == "your-email@example.com" or username.endswith("@example.com"):
            return [
                Warning(
                    "The SMTP username is an example placeholder.",
                    hint="Set DJANGO_EMAIL_HOST_USER and DJANGO_EMAIL_HOST_PASSWORD in .env.",
                    id="inventory.W003",
                )
            ]
        if not settings.EMAIL_HOST_PASSWORD or settings.EMAIL_HOST_PASSWORD == "your-app-password":
            return [
                Warning(
                    "The SMTP password is missing or still a placeholder.",
                    hint="Set DJANGO_EMAIL_HOST_PASSWORD to the sender mailbox app password.",
                    id="inventory.W004",
                )
            ]
    return []


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory"
    verbose_name = "Bluedome Inventory Configuration"

    def ready(self):
        from . import signals  # noqa: F401
