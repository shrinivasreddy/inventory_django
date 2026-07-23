"""
Storage layer for the inventory app, using Django's ORM instead of the
Flask version's flat JSON files. Two models cover everything:

- TabRecord: one row per inventory record (Sign/Pavement/Lane/Curb all
  share this table, distinguished by `tab`). The actual columns vary per
  tab (21 for Sign, 17 for Pavement, etc.), so they're stored as a JSONField
  rather than as fixed database columns -- this keeps the same spec-driven
  design the Flask version used, just persisted differently.

- InventorySection and the normalized option/mapping models hold all editable
  section configuration. JSON files are import seeds only and are never read
  by request handling.
"""

from django.db import models

# Project-scoped inventory access.


class Project(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    members = models.ManyToManyField("auth.User", blank=True, related_name="inventory_projects")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class RegistrationApproval(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = ((STATUS_PENDING, "Pending"), (STATUS_APPROVED, "Approved"), (STATUS_REJECTED, "Rejected"))
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="registration_approval")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_registrations")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.status}"


class InventorySection(models.Model):
    key = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100)
    configuration = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.name


class DropdownOption(models.Model):
    section = models.ForeignKey(InventorySection, on_delete=models.CASCADE, related_name="dropdown_options")
    field_name = models.CharField(max_length=100)
    value = models.CharField(max_length=500)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["section", "field_name", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "field_name", "value"],
                name="unique_section_field_option",
            )
        ]

    def __str__(self):
        return f"{self.section_id} / {self.field_name}: {self.value}"


class AutoFillMapping(models.Model):
    section = models.ForeignKey(InventorySection, on_delete=models.CASCADE, related_name="auto_fill_mappings")
    driver_value = models.CharField(max_length=500)
    values = models.JSONField(default=dict)

    class Meta:
        ordering = ["section", "driver_value"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "driver_value"],
                name="unique_section_auto_fill_driver",
            )
        ]

    def __str__(self):
        return f"{self.section_id}: {self.driver_value}"


class MutcdMapping(models.Model):
    section = models.ForeignKey(InventorySection, on_delete=models.CASCADE, related_name="mutcd_mappings")
    word_description = models.CharField(max_length=500)
    mutcd_code = models.CharField(max_length=200, blank=True)
    classification = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["section", "word_description"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "word_description"],
                name="unique_section_mutcd_word",
            )
        ]

    def __str__(self):
        return self.word_description


class MutcdClassification(models.Model):
    section = models.ForeignKey(InventorySection, on_delete=models.CASCADE, related_name="mutcd_classifications")
    code = models.CharField(max_length=200)
    classification = models.CharField(max_length=300)

    class Meta:
        ordering = ["section", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "code"],
                name="unique_section_mutcd_class",
            )
        ]

    def __str__(self):
        return f"{self.code}: {self.classification}"


class MutcdFallback(models.Model):
    section = models.ForeignKey(InventorySection, on_delete=models.CASCADE, related_name="mutcd_fallbacks")
    code = models.CharField(max_length=200)
    word_description = models.CharField(max_length=500)

    class Meta:
        ordering = ["section", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "code"],
                name="unique_section_mutcd_fallback",
            )
        ]

    def __str__(self):
        return f"{self.code}: {self.word_description}"


class TabRecord(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="inventory_records"
    )
    owner = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_records",
    )
    tab = models.CharField(max_length=20, db_index=True)
    tab_record_id = models.PositiveIntegerField()  # the per-tab sequential "ID" shown to users
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tab", "tab_record_id")]
        ordering = ["tab_record_id"]
        indexes = [
            models.Index(fields=["tab", "tab_record_id"]),
            models.Index(fields=["owner", "tab"], name="inventory_owner_tab_idx"),
            models.Index(fields=["project", "tab"], name="inventory_project_tab_idx"),
        ]

    def as_row(self, include_owner=False):
        row = {**self.data, "ID": self.tab_record_id}
        if include_owner:
            if self.owner:
                row["ADDED_BY"] = self.owner.get_full_name().strip() or self.owner.username
            else:
                row["ADDED_BY"] = "Legacy / unknown"
        return row


class TabState(models.Model):
    """Legacy storage retained for migration compatibility.

    Runtime configuration is served from InventorySection and the normalized
    option/mapping tables above.
    """
    tab = models.CharField(max_length=20, unique=True, db_index=True)
    options = models.JSONField(default=dict)
    mutcd_map = models.JSONField(default=dict)
    mutcd_to_class = models.JSONField(default=dict)
    mutcd_word_fallback = models.JSONField(default=dict)
    mutcd_reverse_map = models.JSONField(default=dict)
    type_map = models.JSONField(default=dict)
