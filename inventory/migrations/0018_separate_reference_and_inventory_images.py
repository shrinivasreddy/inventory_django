from django.db import migrations


def clear_reference_images_from_inventory(apps, schema_editor):
    TabRecord = apps.get_model("inventory", "TabRecord")
    for record in TabRecord.objects.filter(tab="sign").iterator():
        data = dict(record.data or {})
        image_link = str(data.get("IMAGE_LINK", "") or "")
        if "/api/mutcd-reference/" not in image_link:
            continue
        data["IMAGE_LINK"] = ""
        data.pop("_MUTCD_REFERENCE_ID", None)
        record.data = data
        record.save(update_fields=["data"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0017_project_jurisdiction_mutcd_reference"),
    ]

    operations = [
        migrations.RunPython(clear_reference_images_from_inventory, migrations.RunPython.noop),
    ]
