from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.conf import settings
from zipfile import BadZipFile, LargeZipFile, ZipFile

from .models import (
    FrameRangeAssignment,
    InventorySection,
    Project,
    RegistrationApproval,
    TabRecord,
)


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


class FrameRangeAssignmentForm(forms.ModelForm):
    start_frame = forms.TypedChoiceField(
        coerce=int,
        label="Start Frame",
        help_text="Only currently unassigned AI frames are available.",
    )
    end_frame = forms.TypedChoiceField(
        coerce=int,
        label="End Frame",
        help_text="The complete selected range must remain unassigned.",
    )

    class Meta:
        model = FrameRangeAssignment
        fields = ("project", "user", "start_frame", "end_frame")

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        selected_project = project or getattr(self.instance, "project", None)
        if selected_project is None:
            project_id = self.data.get("project") if self.is_bound else self.initial.get("project")
            if project_id:
                selected_project = (
                    project_id
                    if isinstance(project_id, Project)
                    else Project.objects.filter(pk=project_id).first()
                )
        self.project = selected_project
        if project is not None and "project" in self.fields:
            self.fields["project"].required = False
            self.fields["project"].initial = project.pk
        if self.project and not self.instance.project_id:
            self.instance.project = self.project
        self.fields["user"].queryset = User.objects.none()
        available = []
        if self.project and self.project.pk:
            self.fields["user"].queryset = self.project.members.order_by("username")
            assigned_ranges = list(
                FrameRangeAssignment.objects.filter(project=self.project)
                .exclude(pk=self.instance.pk)
                .values_list("start_frame", "end_frame")
            )
            available = list(
                TabRecord.objects.filter(
                    project=self.project,
                    is_ai_processed=True,
                    ai_frame__isnull=False,
                )
                .order_by("ai_frame")
                .values_list("ai_frame", flat=True)
                .distinct()
            )
            available = [
                frame for frame in available
                if not any(start <= frame <= end for start, end in assigned_ranges)
            ]
            if self.instance.pk:
                available.extend([self.instance.start_frame, self.instance.end_frame])

        choices = [(frame, str(frame)) for frame in sorted(set(available))]
        empty = [("", "Select an unassigned frame")]
        self.fields["start_frame"].choices = empty + choices
        self.fields["end_frame"].choices = empty + choices

    def clean_project(self):
        return self.cleaned_data.get("project") or self.project

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_frame")
        end = cleaned.get("end_frame")
        if start is not None and end is not None and start > end:
            raise forms.ValidationError("Start Frame must be less than or equal to End Frame.")
        return cleaned


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
            RegistrationApproval.objects.get_or_create(user=user)
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


class AIProcessedImportForm(forms.Form):
    section = forms.ChoiceField(
        choices=(
            ("sign", "Sign Inventory"),
            ("pavement", "Pavement Inventory"),
            ("lane", "Lane Inventory"),
            ("curb", "Curb Inventory"),
        ),
        help_text="Sign mapping is active. Other mappings can be added when sample files are available.",
    )
    data_file = forms.FileField(
        label="AI processed CSV or Excel file",
        help_text="Upload a .csv or .xlsx file (maximum 20 MB).",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,.xlsx"}),
    )
    excluded_codes = forms.CharField(
        required=False,
        label="Exclude CODE values for this upload",
        help_text="One value per line or comma-separated. Changes here do not update the saved default.",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "NULL\nNOT SIGN\nOTHER"}),
    )

    def clean_data_file(self):
        upload = self.cleaned_data["data_file"]
        suffix = upload.name.lower().rsplit(".", 1)[-1] if "." in upload.name else ""
        if suffix not in {"csv", "xlsx"}:
            raise forms.ValidationError("Only .csv and .xlsx files are supported.")
        if upload.size > settings.MAX_XLSX_UPLOAD_BYTES:
            raise forms.ValidationError("The file must be 20 MB or smaller.")
        if suffix == "xlsx":
            validate_xlsx_upload(upload)
        return upload

    def clean_excluded_codes(self):
        value = self.cleaned_data.get("excluded_codes", "")
        return sorted({item.strip().upper() for item in value.replace(",", "\n").splitlines() if item.strip()})


class AIExclusionSettingsForm(forms.Form):
    historical_codes = forms.MultipleChoiceField(
        required=False,
        label="Previously seen CODE values",
        widget=forms.CheckboxSelectMultiple,
    )
    manual_codes = forms.CharField(
        required=False,
        label="Additional exclusion values",
        help_text="Enter values not shown above, one per line or comma-separated.",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "NEW VALUE"}),
    )

    def __init__(self, *args, historical_codes=(), selected_codes=(), **kwargs):
        super().__init__(*args, **kwargs)
        historical = sorted({str(code).strip().upper() for code in historical_codes if str(code).strip()})
        selected = {str(code).strip().upper() for code in selected_codes if str(code).strip()}
        self.fields["historical_codes"].choices = [(code, code) for code in historical]
        if not self.is_bound:
            self.initial["historical_codes"] = sorted(selected.intersection(historical))
            self.initial["manual_codes"] = "\n".join(sorted(selected.difference(historical)))

    def exclusion_codes(self):
        historical = self.cleaned_data.get("historical_codes", [])
        manual = self.cleaned_data.get("manual_codes", "")
        return sorted({
            item.strip().upper()
            for item in list(historical) + manual.replace(",", "\n").splitlines()
            if item.strip()
        })
