from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


strict_email_validator = RegexValidator(
    regex=r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$",
    message="Enter a valid email address, for example name@example.com.",
)
strict_email_widget = forms.EmailInput(
    attrs={
        "autocomplete": "email",
        "inputmode": "email",
        "pattern": r"[^@\s]+@[^@\s]+\.[^@\s]{2,}",
        "title": "Enter a valid email address, for example name@example.com.",
    }
)


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        validators=[strict_email_validator],
        widget=strict_email_widget,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class PasswordResetRequestForm(PasswordResetForm):
    email = forms.EmailField(
        required=True,
        validators=[strict_email_validator],
        widget=strict_email_widget,
    )
