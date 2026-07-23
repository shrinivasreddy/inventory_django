from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.conf import settings
from zipfile import BadZipFile, LargeZipFile, ZipFile

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


def validate_xlsx_upload(uploaded_file):
    if not uploaded_file.name.lower().endswith(".xlsx"):
        raise forms.ValidationError("Only .xlsx Excel workbooks are supported.")
    if uploaded_file.size > settings.MAX_XLSX_UPLOAD_BYTES:
        raise forms.ValidationError("The workbook must be 20 MB or smaller.")
    try:
        with ZipFile(uploaded_file) as archive:
            entries = archive.infolist()
            if len(entries) > settings.MAX_XLSX_ARCHIVE_ENTRIES:
                raise forms.ValidationError("The workbook contains too many internal files.")
            if any(entry.flag_bits & 0x1 for entry in entries):
                raise forms.ValidationError("Password-protected workbooks are not supported.")
            if sum(entry.file_size for entry in entries) > settings.MAX_XLSX_UNCOMPRESSED_BYTES:
                raise forms.ValidationError("The workbook expands beyond the safe processing limit.")
    except (BadZipFile, LargeZipFile, OSError):
        raise forms.ValidationError("The uploaded file is not a valid .xlsx workbook.")
    finally:
        uploaded_file.seek(0)
    return uploaded_file


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
        user.is_active = False
        if commit:
            user.save()
        return user


class ApprovalAuthenticationForm(AuthenticationForm):
    """Explain inactive-account failures only after the password is verified."""

    inactive_message = (
        "Your account is pending administrator approval or has been deactivated. "
        "Please contact an administrator."
    )

    def clean(self):
        try:
            return super().clean()
        except ValidationError as error:
            username = self.data.get("username", "")
            password = self.data.get("password", "")
            user = User.objects.filter(username__iexact=username).first()
            if user and not user.is_active and user.check_password(password):
                raise ValidationError(self.inactive_message, code="inactive")
            raise error


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
        return validate_xlsx_upload(self.cleaned_data["excel_file"])


class ConfigurationExcelImportForm(forms.Form):
    excel_file = forms.FileField(
        label="Excel workbook",
        help_text="Upload an .xlsx file created from the downloadable template.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )

    def clean_excel_file(self):
        return validate_xlsx_upload(self.cleaned_data["excel_file"])
