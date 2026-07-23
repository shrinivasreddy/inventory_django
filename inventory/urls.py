from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import ApprovalAuthenticationForm, PasswordResetRequestForm

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=ApprovalAuthenticationForm,
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("signup/pending/", views.signup_pending, name="signup_pending"),
    path(
        "signup/password-requirements/",
        views.password_requirements,
        name="password_requirements",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=PasswordResetRequestForm,
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("", views.home, name="home"),
    path("api/assistant/preview", views.api_assistant_preview, name="api_assistant_preview"),
    path(
        "api/assistant/transcribe",
        views.api_assistant_transcribe,
        name="api_assistant_transcribe",
    ),
    path("api/export_all", views.api_export_all, name="api_export_all"),
    path("api/<str:key>/spec", views.api_spec, name="api_spec"),
    path("api/<str:key>/records", views.api_records, name="api_records"),
    path("api/<str:key>/records/<int:rec_id>", views.api_record_detail, name="api_record_detail"),
    path("api/<str:key>/records/<int:rec_id>/image", views.api_record_image, name="api_record_image"),
    path(
        "uploads/images/<str:folder>/<int:rec_id>/<str:filename>",
        views.inventory_image,
        name="inventory_image",
    ),
    path("api/<str:key>/options", views.api_options, name="api_options"),
    path("api/<str:key>/export", views.api_export, name="api_export"),
]
