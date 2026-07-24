from django.db import migrations, models


def populate_display_order(apps, schema_editor):
    TabRecord = apps.get_model("inventory", "TabRecord")
    records = TabRecord.objects.order_by("project_id", "tab", "tab_record_id", "pk")
    current_group = None
    position = 0
    for record in records.iterator():
        group = (record.project_id, record.tab)
        if group != current_group:
            current_group = group
            position = 1
        else:
            position += 1
        record.display_order = position
        record.save(update_fields=["display_order"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0009_registrationapproval")]

    operations = [
        migrations.AlterModelOptions(
            name="tabrecord",
            options={"ordering": ["display_order", "tab_record_id"]},
        ),
        migrations.AddField(
            model_name="tabrecord",
            name="display_order",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(populate_display_order, migrations.RunPython.noop),
    ]
