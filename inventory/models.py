"""
Storage layer for the inventory app, using Django's ORM instead of the
Flask version's flat JSON files. Two models cover everything:

- TabRecord: one row per inventory record (Sign/Pavement/Lane/Curb all
  share this table, distinguished by `tab`). The actual columns vary per
  tab (21 for Sign, 17 for Pavement, etc.), so they're stored as a JSONField
  rather than as fixed database columns -- this keeps the same spec-driven
  design the Flask version used, just persisted differently.

- TabState: one row per tab, holding its dropdown options, MUTCD tables,
  and auto-fill type-map. This is the direct database equivalent of the
  Flask version's in-memory `state[key]` dict.
"""

from django.db import models


class TabRecord(models.Model):
    tab = models.CharField(max_length=20, db_index=True)
    tab_record_id = models.PositiveIntegerField()  # the per-tab sequential "ID" shown to users
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tab", "tab_record_id")]
        ordering = ["tab_record_id"]
        indexes = [models.Index(fields=["tab", "tab_record_id"])]

    def as_row(self):
        return {**self.data, "ID": self.tab_record_id}


class TabState(models.Model):
    tab = models.CharField(max_length=20, unique=True, db_index=True)
    options = models.JSONField(default=dict)
    mutcd_map = models.JSONField(default=dict)
    mutcd_to_class = models.JSONField(default=dict)
    mutcd_word_fallback = models.JSONField(default=dict)
    mutcd_reverse_map = models.JSONField(default=dict)
    type_map = models.JSONField(default=dict)
