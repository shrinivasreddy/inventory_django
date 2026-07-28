from django.db import migrations


def remove_legacy_ai_other_records(apps, schema_editor):
    """Remove placeholder detections imported before OTHER became excluded."""
    TabRecord = apps.get_model("inventory", "TabRecord")
    stale_ids = []

    for record in TabRecord.objects.filter(tab="sign").only("pk", "data").iterator():
        data = record.data or {}
        if not data.get("_AI_PROCESSED"):
            continue
        if str(data.get("MUTCD", "")).strip().upper() != "OTHER":
            continue

        stale_ids.append(record.pk)
        if len(stale_ids) >= 500:
            TabRecord.objects.filter(pk__in=stale_ids).delete()
            stale_ids.clear()

    if stale_ids:
        TabRecord.objects.filter(pk__in=stale_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0014_aiimportsettings_aiobservedcode"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_ai_other_records, migrations.RunPython.noop),
    ]
