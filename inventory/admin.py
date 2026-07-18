from django.contrib import admin
from .models import TabRecord, TabState


@admin.register(TabRecord)
class TabRecordAdmin(admin.ModelAdmin):
    list_display = ("tab", "tab_record_id", "updated_at")
    list_filter = ("tab",)
    search_fields = ("tab_record_id",)
    ordering = ("tab", "tab_record_id")


@admin.register(TabState)
class TabStateAdmin(admin.ModelAdmin):
    list_display = ("tab",)
