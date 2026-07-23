import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .image_storage import delete_record_image_directory
from .models import TabRecord


logger = logging.getLogger(__name__)
User = get_user_model()


def smtp_configuration_error():
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        return "SMTP is not configured; the console email backend cannot deliver messages."
    if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
        return None
    host = (settings.EMAIL_HOST or "").strip().lower()
    username = (settings.EMAIL_HOST_USER or "").strip().lower()
    password = settings.EMAIL_HOST_PASSWORD or ""
    if not host or host == "smtp.example.com" or host.endswith(".example.com"):
        return "SMTP host is still a placeholder. Set DJANGO_EMAIL_HOST to your provider's real SMTP server."
    if not username or username == "your-email@example.com" or username.endswith("@example.com"):
        return "SMTP username is still a placeholder. Set DJANGO_EMAIL_HOST_USER to the sender mailbox."
    if not password or password == "your-app-password":
        return "SMTP password is missing. Set DJANGO_EMAIL_HOST_PASSWORD to the mailbox app password."
    return None


def send_account_approved_email(user_id):
    message = smtp_configuration_error()
    if message:
        logger.warning("Approval email not delivered for user ID %s: %s", user_id, message)
        return False, message
    try:
        user = User.objects.get(pk=user_id, is_active=True)
        if not user.email:
            message = "The approved user has no email address."
            logger.warning("Approved user %s has no email address.", user.username)
            return False, message
        login_url = f"{settings.APP_BASE_URL.rstrip('/')}/login/"
        delivered = send_mail(
            "Bluedome Inventory account approved",
            (
                f"Hello {user.get_full_name().strip() or user.username},\n\n"
                "Your Bluedome Inventory account has been approved and is now active.\n"
                f"You can start using the application here: {login_url}\n\n"
                "If you did not request this account, please contact your administrator."
            ),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        if delivered == 1:
            return True, f"Approval email sent to {user.email}."
        return False, "The email backend did not accept the approval message."
    except User.DoesNotExist:
        return False, "The activated user could not be found."
    except Exception as error:
        logger.exception("Could not send account approval email for user ID %s.", user_id)
        return False, f"Approval email failed: {error}"


def send_account_deactivated_email(user_id):
    message = smtp_configuration_error()
    if message:
        logger.warning("Deactivation email not delivered for user ID %s: %s", user_id, message)
        return False, message
    try:
        user = User.objects.get(pk=user_id)
        if not user.email:
            message = "The deactivated user has no email address."
            logger.warning("Deactivated user %s has no email address.", user.username)
            return False, message
        delivered = send_mail(
            "Bluedome Inventory account deactivated",
            (
                f"Hello {user.get_full_name().strip() or user.username},\n\n"
                "Your Bluedome Inventory account has been deactivated and can no longer "
                "access the application.\n\n"
                "If you believe this was a mistake, please contact your administrator."
            ),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        if delivered == 1:
            return True, f"Deactivation email sent to {user.email}."
        return False, "The email backend did not accept the deactivation message."
    except User.DoesNotExist:
        return False, "The deactivated user could not be found."
    except Exception as error:
        logger.exception("Could not send account deactivation email for user ID %s.", user_id)
        return False, f"Deactivation email failed: {error}"


@receiver(pre_save, sender=User)
def remember_previous_active_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._was_active = None
        return
    instance._was_active = (
        sender.objects.filter(pk=instance.pk).values_list("is_active", flat=True).first()
    )


@receiver(post_save, sender=User)
def notify_newly_approved_user(sender, instance, created, **kwargs):
    if (
        not created
        and instance.is_active
        and getattr(instance, "_was_active", None) is False
        and not getattr(instance, "_skip_approval_email", False)
    ):
        transaction.on_commit(lambda: send_account_approved_email(instance.pk))
    if (
        not created
        and not instance.is_active
        and getattr(instance, "_was_active", None) is True
        and not getattr(instance, "_skip_deactivation_email", False)
    ):
        transaction.on_commit(lambda: send_account_deactivated_email(instance.pk))


@receiver(post_delete, sender=TabRecord)
def remove_deleted_record_image(sender, instance, **kwargs):
    transaction.on_commit(
        lambda: delete_record_image_directory(instance.tab, instance.tab_record_id)
    )
