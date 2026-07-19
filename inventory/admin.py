from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    AutoFillMapping,
    DropdownOption,
    InventorySection,
    MutcdClassification,
    MutcdFallback,
    MutcdMapping,
    TabRecord,
)

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
class DropdownOptionAdmin(RowActionsAdminMixin, admin.ModelAdmin):
    list_display = ("section", "field_name", "value", "sort_order", "row_actions")
    list_filter = ("section", "field_name")
    search_fields = ("field_name", "value")
    ordering = ("section", "field_name", "sort_order", "id")


@admin.register(AutoFillMapping)
class AutoFillMappingAdmin(RowActionsAdminMixin, admin.ModelAdmin):
    list_display = ("section", "driver_value", "row_actions")
    list_filter = ("section",)
    search_fields = ("driver_value",)


@admin.register(MutcdMapping)
class MutcdMappingAdmin(RowActionsAdminMixin, admin.ModelAdmin):
    list_display = ("word_description", "mutcd_code", "classification", "section", "row_actions")
    list_filter = ("section", "classification")
    search_fields = ("word_description", "mutcd_code", "classification")


@admin.register(MutcdClassification)
class MutcdClassificationAdmin(RowActionsAdminMixin, admin.ModelAdmin):
    list_display = ("code", "classification", "section", "row_actions")
    list_filter = ("section", "classification")
    search_fields = ("code", "classification")


@admin.register(MutcdFallback)
class MutcdFallbackAdmin(RowActionsAdminMixin, admin.ModelAdmin):
    list_display = ("code", "word_description", "section", "row_actions")
    list_filter = ("section",)
    search_fields = ("code", "word_description")


@admin.register(TabRecord)
class TabRecordAdmin(admin.ModelAdmin):
    list_display = ("tab", "tab_record_id", "updated_at")
    list_filter = ("tab",)
    search_fields = ("tab_record_id",)
    ordering = ("tab", "tab_record_id")
