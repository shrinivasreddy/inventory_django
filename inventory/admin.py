import io
import json
from datetime import date, datetime
from zipfile import BadZipFile

from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .forms import ConfigurationExcelImportForm, InventoryExcelImportForm
from .models import (
    AutoFillMapping,
    DropdownOption,
    InventorySection,
    MutcdClassification,
    MutcdFallback,
    MutcdMapping,
    TabRecord,
)
from .specs import TAB_ORDER, compute_auto_fields, get_section_state, get_spec, missing_required_fields

admin.site.site_header = "Bluedome Inventory"
admin.site.site_title = "Bluedome Inventory"
admin.site.index_title = "Inventory Configuration"
admin.site.site_url = "/"


class RowActionsAdminMixin:
    """Expose explicit, permission-aware row actions in each change list."""

    @admin.display(description="Actions")
    def row_actions(self, obj):
        opts = obj._meta
        change_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change",
            args=[obj.pk],
        )
        delete_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_delete",
            args=[obj.pk],
        )
        return format_html(
            '<a class="row-action row-action-edit" href="{}" '
            'title="Edit" aria-label="Edit">'
            '<svg aria-hidden="true" viewBox="0 0 24 24">'
            '<path d="M4 16.5V20h3.5L18 9.5 14.5 6 4 16.5zm16.7-9.8a1 1 0 0 0 '
            '0-1.4l-2-2a1 1 0 0 0-1.4 0L15.5 5l3.5 3.5 1.7-1.8z"/></svg>'
            '<span class="sr-only">Edit</span></a>'
            '<a class="row-action row-action-delete" href="{}" '
            'title="Delete" aria-label="Delete">'
            '<svg aria-hidden="true" viewBox="0 0 24 24">'
            '<path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM8 '
            '9h8v10H8V9zm7.5-5-1-1h-5l-1 1H5v2h14V4z"/></svg>'
            '<span class="sr-only">Delete</span></a>',
            change_url,
            delete_url,
        )


class ConfigurationExcelAdminMixin:
    """Bulk Excel import/export for normalized admin configuration tables."""

    change_list_template = "admin/inventory/configuration_change_list.html"
    change_form_template = "admin/inventory/configuration_change_form.html"
    excel_columns = ()
    excel_unique_fields = ()
    excel_json_fields = ()

    def get_urls(self):
        opts = self.model._meta
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name=f"{opts.app_label}_{opts.model_name}_import_excel",
            ),
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel),
                name=f"{opts.app_label}_{opts.model_name}_export_excel",
            ),
            path(
                "excel-template/",
                self.admin_site.admin_view(self.excel_template),
                name=f"{opts.app_label}_{opts.model_name}_excel_template",
            ),
        ]
        return custom_urls + urls

    def _excel_url(self, action):
        opts = self.model._meta
        suffix = {
            "import": "import_excel",
            "export": "export_excel",
            "template": "excel_template",
        }[action]
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_{suffix}")

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "excel_import_url": self._excel_url("import"),
            "excel_export_url": self._excel_url("export"),
            "excel_template_url": self._excel_url("template"),
        }
        return super().changelist_view(request, extra_context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "excel_import_url": self._excel_url("import"),
            "excel_export_url": self._excel_url("export"),
            "excel_template_url": self._excel_url("template"),
        }
        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context,
        )

    @staticmethod
    def _cell_value(value):
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _workbook(self, include_records):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = self.model._meta.verbose_name_plural.title()[:31]
        headers = [label for label, _field in self.excel_columns]
        TabRecordAdmin._style_sheet(worksheet, headers)
        if include_records:
            for obj in self.get_queryset(None).order_by(*self.model._meta.ordering):
                row = []
                for _label, field_name in self.excel_columns:
                    if field_name == "section":
                        value = obj.section_id
                    else:
                        value = getattr(obj, field_name)
                    if field_name in self.excel_json_fields:
                        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                    row.append(value)
                worksheet.append(row)
        return workbook

    def _workbook_response(self, workbook, filename):
        output = io.BytesIO()
        workbook.save(output)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def excel_template(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        return self._workbook_response(
            self._workbook(include_records=False),
            f"{self.model._meta.model_name}-import-template.xlsx",
        )

    def export_excel(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        return self._workbook_response(
            self._workbook(include_records=True),
            f"{self.model._meta.model_name}-all-records.xlsx",
        )

    def import_excel(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        opts = self.model._meta
        if request.method == "POST":
            form = ConfigurationExcelImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    workbook = load_workbook(
                        form.cleaned_data["excel_file"],
                        read_only=True,
                        data_only=True,
                    )
                except (BadZipFile, InvalidFileException, OSError, ValueError):
                    form.add_error("excel_file", "The uploaded file is not a valid Excel workbook.")
                else:
                    worksheet = workbook.active
                    expected_headers = [label for label, _field in self.excel_columns]
                    headers = [
                        self._cell_value(value)
                        for value in next(
                            worksheet.iter_rows(min_row=1, max_row=1, values_only=True),
                            (),
                        )
                    ]
                    while headers and not headers[-1]:
                        headers.pop()
                    errors = []
                    if headers != expected_headers:
                        errors.append(
                            "The headers must exactly match the downloaded template: "
                            + ", ".join(expected_headers)
                        )
                    pending = []
                    seen = set()
                    if not errors:
                        for row_number, values in enumerate(
                            worksheet.iter_rows(min_row=2, values_only=True),
                            start=2,
                        ):
                            if row_number > 10001:
                                errors.append("A maximum of 10,000 rows can be imported at once.")
                                break
                            if not any(value not in (None, "") for value in values):
                                continue
                            data = {}
                            for index, (_label, field_name) in enumerate(self.excel_columns):
                                value = self._cell_value(
                                    values[index] if index < len(values) else ""
                                )
                                if field_name == "section":
                                    data["section_id"] = value.lower()
                                elif field_name in self.excel_json_fields:
                                    try:
                                        data[field_name] = json.loads(value or "{}")
                                    except json.JSONDecodeError:
                                        errors.append(
                                            f"Row {row_number}: {field_name} must contain valid JSON."
                                        )
                                elif self.model._meta.get_field(field_name).get_internal_type() in {
                                    "IntegerField",
                                    "PositiveIntegerField",
                                }:
                                    try:
                                        data[field_name] = int(value or 0)
                                    except ValueError:
                                        errors.append(
                                            f"Row {row_number}: {field_name} must be a whole number."
                                        )
                                else:
                                    data[field_name] = value
                            unique_key = tuple(
                                data.get("section_id" if field == "section" else field)
                                for field in self.excel_unique_fields
                            )
                            if unique_key in seen:
                                errors.append(f"Row {row_number}: duplicate record in workbook.")
                            seen.add(unique_key)
                            obj = self.model(**data)
                            try:
                                obj.full_clean()
                            except ValidationError as exc:
                                details = "; ".join(
                                    f"{field}: {', '.join(messages)}"
                                    for field, messages in exc.message_dict.items()
                                )
                                errors.append(f"Row {row_number}: {details}")
                            pending.append(obj)
                    if errors:
                        form.add_error(None, errors[:25])
                    elif not pending:
                        form.add_error(None, "The workbook does not contain any data rows.")
                    else:
                        try:
                            with transaction.atomic():
                                self.model.objects.bulk_create(pending)
                        except IntegrityError:
                            form.add_error(
                                None,
                                "The import conflicts with data saved by another request. "
                                "Export the latest data and try again.",
                            )
                        else:
                            messages.success(
                                request,
                                f"Successfully imported {len(pending)} {opts.verbose_name_plural}.",
                            )
                            return redirect(
                                reverse(
                                    f"admin:{opts.app_label}_{opts.model_name}_changelist"
                                )
                            )
        else:
            form = ConfigurationExcelImportForm()
        return render(
            request,
            "admin/inventory/configuration_import_excel.html",
            {
                **self.admin_site.each_context(request),
                "form": form,
                "title": f"Import {opts.verbose_name_plural}",
                "opts": opts,
                "changelist_url": reverse(
                    f"admin:{opts.app_label}_{opts.model_name}_changelist"
                ),
                "template_url": self._excel_url("template"),
                "export_url": self._excel_url("export"),
            },
        )
@admin.register(InventorySection)
class InventorySectionAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "updated_at")
    search_fields = ("name", "key")
    readonly_fields = ("key", "updated_at")

    def has_add_permission(self, request):
        # The four supported sections are created by the seed migration.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DropdownOption)
class DropdownOptionAdmin(ConfigurationExcelAdminMixin, RowActionsAdminMixin, admin.ModelAdmin):
    excel_columns = (
        ("Section", "section"),
        ("Field name", "field_name"),
        ("Value", "value"),
        ("Sort order", "sort_order"),
    )
    excel_unique_fields = ("section", "field_name", "value")
    list_display = ("section", "field_name", "value", "sort_order", "row_actions")
    list_filter = ("section", "field_name")
    search_fields = ("field_name", "value")
    ordering = ("section", "field_name", "sort_order", "id")


@admin.register(AutoFillMapping)
class AutoFillMappingAdmin(ConfigurationExcelAdminMixin, RowActionsAdminMixin, admin.ModelAdmin):
    excel_columns = (
        ("Section", "section"),
        ("Driver value", "driver_value"),
        ("Values JSON", "values"),
    )
    excel_unique_fields = ("section", "driver_value")
    excel_json_fields = ("values",)
    list_display = ("section", "driver_value", "row_actions")
    list_filter = ("section",)
    search_fields = ("driver_value",)


@admin.register(MutcdMapping)
class MutcdMappingAdmin(ConfigurationExcelAdminMixin, RowActionsAdminMixin, admin.ModelAdmin):
    excel_columns = (
        ("Section", "section"),
        ("Word description", "word_description"),
        ("MUTCD code", "mutcd_code"),
        ("Classification", "classification"),
    )
    excel_unique_fields = ("section", "word_description")
    list_display = ("word_description", "mutcd_code", "classification", "section", "row_actions")
    list_filter = ("section", "classification")
    search_fields = ("word_description", "mutcd_code", "classification")


@admin.register(MutcdClassification)
class MutcdClassificationAdmin(
    ConfigurationExcelAdminMixin,
    RowActionsAdminMixin,
    admin.ModelAdmin,
):
    excel_columns = (
        ("Section", "section"),
        ("MUTCD code", "code"),
        ("Classification", "classification"),
    )
    excel_unique_fields = ("section", "code")
    list_display = ("code", "classification", "section", "row_actions")
    list_filter = ("section", "classification")
    search_fields = ("code", "classification")


@admin.register(MutcdFallback)
class MutcdFallbackAdmin(ConfigurationExcelAdminMixin, RowActionsAdminMixin, admin.ModelAdmin):
    excel_columns = (
        ("Section", "section"),
        ("MUTCD code", "code"),
        ("Word description", "word_description"),
    )
    excel_unique_fields = ("section", "code")
    list_display = ("code", "word_description", "section", "row_actions")
    list_filter = ("section",)
    search_fields = ("code", "word_description")


@admin.register(TabRecord)
class TabRecordAdmin(admin.ModelAdmin):
    list_display = ("tab", "tab_record_id", "updated_at")
    list_filter = ("tab",)
    search_fields = ("tab_record_id",)
    ordering = ("tab", "tab_record_id")
    change_list_template = "admin/inventory/tabrecord/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="inventory_tabrecord_import_excel",
            ),
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel),
                name="inventory_tabrecord_export_excel",
            ),
            path(
                "excel-template/",
                self.admin_site.admin_view(self.excel_template),
                name="inventory_tabrecord_excel_template",
            ),
        ]
        return custom_urls + urls

    @staticmethod
    def _excel_value(value):
        if value is None:
            return ""
        if isinstance(value, (datetime, date)):
            return value.strftime("%m-%d-%Y")
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    @staticmethod
    def _style_sheet(ws, columns):
        header_fill = PatternFill("solid", fgColor="305496")
        header_font = Font(bold=True, color="FFFFFF")
        for index, column in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=index, value=column)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[get_column_letter(index)].width = max(14, min(35, len(column) + 4))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}1"

    def import_excel(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        if request.method == "POST":
            form = InventoryExcelImportForm(request.POST, request.FILES)
            if form.is_valid():
                section_key = form.cleaned_data["section"].key
                spec = get_spec(section_key)
                try:
                    workbook = load_workbook(
                        form.cleaned_data["excel_file"],
                        read_only=True,
                        data_only=True,
                    )
                except (BadZipFile, InvalidFileException, OSError, ValueError):
                    form.add_error("excel_file", "The uploaded file is not a valid Excel workbook.")
                else:
                    sheet_name = spec["export_sheet_name"]
                    worksheet = (
                        workbook[sheet_name]
                        if sheet_name in workbook.sheetnames
                        else workbook.active
                    )
                    raw_headers = next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
                    headers = [self._excel_value(value) for value in raw_headers]
                    while headers and not headers[-1]:
                        headers.pop()
                    duplicate_headers = {header for header in headers if header and headers.count(header) > 1}
                    unknown_headers = [header for header in headers if header and header not in spec["columns"]]
                    missing_uid_headers = [field for field in spec["uid_parts"] if field not in headers]

                    errors = []
                    if not headers:
                        errors.append("The workbook does not contain a header row.")
                    if duplicate_headers:
                        errors.append("Duplicate headers: " + ", ".join(sorted(duplicate_headers)))
                    if unknown_headers:
                        errors.append("Unknown headers: " + ", ".join(unknown_headers))
                    if missing_uid_headers:
                        errors.append("Required headers are missing: " + ", ".join(missing_uid_headers))

                    pending_rows = []
                    state = get_section_state(section_key)
                    if not errors:
                        for excel_row_number, values in enumerate(
                            worksheet.iter_rows(min_row=2, values_only=True),
                            start=2,
                        ):
                            if excel_row_number > 10001:
                                errors.append("A maximum of 10,000 data rows can be imported at once.")
                                break
                            if not any(value not in (None, "") for value in values):
                                continue
                            supplied = {
                                header: self._excel_value(values[index] if index < len(values) else "")
                                for index, header in enumerate(headers)
                                if header and header != "ID"
                            }
                            row = {
                                column: supplied.get(column, "")
                                for column in spec["columns"]
                                if column != "ID"
                            }
                            row = compute_auto_fields(section_key, row, state)
                            missing = missing_required_fields(section_key, row)
                            if missing:
                                errors.append(
                                    f"Row {excel_row_number}: missing required values "
                                    + ", ".join(missing)
                                )
                            pending_rows.append(row)

                    if errors:
                        form.add_error(None, errors[:25])
                    elif not pending_rows:
                        form.add_error(None, "The workbook does not contain any data rows.")
                    else:
                        try:
                            with transaction.atomic():
                                max_id = (
                                    TabRecord.objects.filter(tab=section_key)
                                    .aggregate(value=Max("tab_record_id"))["value"]
                                    or 0
                                )
                                TabRecord.objects.bulk_create(
                                    [
                                        TabRecord(
                                            tab=section_key,
                                            tab_record_id=max_id + offset,
                                            data=row,
                                        )
                                        for offset, row in enumerate(pending_rows, start=1)
                                    ]
                                )
                        except IntegrityError:
                            form.add_error(
                                None,
                                "The import conflicts with inventory records saved by "
                                "another request. Export the latest data and try again.",
                            )
                        else:
                            self.message_user(
                                request,
                                f"Successfully imported {len(pending_rows)} "
                                f"{spec['tab_label']} records.",
                                messages.SUCCESS,
                            )
                            return redirect("admin:inventory_tabrecord_changelist")
        else:
            form = InventoryExcelImportForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Import inventory records from Excel",
            "form": form,
            "opts": self.model._meta,
        }
        return render(request, "admin/inventory/tabrecord/import_excel.html", context)

    def excel_template(self, request):
        workbook = Workbook()
        workbook.remove(workbook.active)
        for section_key in TAB_ORDER:
            spec = get_spec(section_key)
            ws = workbook.create_sheet(spec["export_sheet_name"])
            self._style_sheet(ws, spec["columns"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="Bluedome_Inventory_Import_Template.xlsx"'
        return response

    def export_excel(self, request):
        workbook = Workbook()
        workbook.remove(workbook.active)
        record_count = 0
        for section_key in TAB_ORDER:
            spec = get_spec(section_key)
            records = list(TabRecord.objects.filter(tab=section_key).order_by("tab_record_id"))
            ws = workbook.create_sheet(spec["export_sheet_name"])
            self._style_sheet(ws, spec["columns"])
            for record in records:
                row = record.as_row()
                ws.append([row.get(column, "") for column in spec["columns"]])
            record_count += len(records)
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="Bluedome_All_Inventory_Records_{date.today().isoformat()}.xlsx"'
        )
        response["X-Record-Count"] = str(record_count)
        return response
