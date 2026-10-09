from django.db import migrations


def uppercase_columns(apps, schema_editor):
    for model_name in ("TabRecord", "StagedInventoryRecord"):
        model = apps.get_model("inventory", model_name)
        for record in model.objects.using(schema_editor.connection.alias).filter(tab="sign").iterator():
            data = dict(record.data)
            changed = False
            for old, new in (("image", "IMAGE"), ("rename", "RENAME")):
                if old in data:
                    # Preserve existing AI IMAGE metadata if already populated.
                    if not data.get(new):
                        data[new] = data[old]
                    if data[new] == data[old]:
                        del data[old]
                    changed = True
            if changed:
                record.data = data
                record.save(update_fields=["data"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0025_userprofile_delegated_admin")]
    operations = [migrations.RunPython(uppercase_columns, migrations.RunPython.noop)]
