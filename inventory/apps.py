from django.apps import AppConfig
from django.core.checks import Warning, register
from django.conf import settings


@register("security", deploy=True)
def password_reset_email_backend_check(app_configs, **kwargs):
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        return [
            Warning(
                "Password-reset emails are using the console backend and will "
                "not be delivered to users.",
                hint=(
                    "Configure DJANGO_EMAIL_BACKEND and the DJANGO_EMAIL_* SMTP "
                    "settings documented in .env.example."
                ),
                id="inventory.W001",
            )
        ]
    return []


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory"
    verbose_name = "Bluedome Inventory Configuration"
