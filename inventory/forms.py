from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

from .models import InventorySection


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


class InventoryExcelImportForm(forms.Form):
    section = forms.ModelChoiceField(
        queryset=InventorySection.objects.all().order_by("name"),
        empty_label="Select an inventory section",
    )
    excel_file = forms.FileField(
        label="Excel workbook",
        help_text="Upload an .xlsx file. The first row must contain field names.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )

    def clean_excel_file(self):
        uploaded_file = self.cleaned_data["excel_file"]
        if not uploaded_file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Only .xlsx Excel workbooks are supported.")
        if uploaded_file.size > 20 * 1024 * 1024:
            raise forms.ValidationError("The workbook must be 20 MB or smaller.")
        return uploaded_file


class ConfigurationExcelImportForm(forms.Form):
    excel_file = forms.FileField(
        label="Excel workbook",
        help_text="Upload an .xlsx file created from the downloadable template.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )

    def clean_excel_file(self):
        uploaded_file = self.cleaned_data["excel_file"]
        if not uploaded_file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Only .xlsx Excel workbooks are supported.")
        if uploaded_file.size > 20 * 1024 * 1024:
            raise forms.ValidationError("The workbook must be 20 MB or smaller.")
        return uploaded_file
