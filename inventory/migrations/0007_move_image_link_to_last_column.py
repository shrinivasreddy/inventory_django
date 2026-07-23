from django.db import migrations


def move_image_link_last(apps, schema_editor):
    InventorySection = apps.get_model("inventory", "InventorySection")
    for section in InventorySection.objects.filter(
        key__in=["sign", "pavement", "lane", "curb"]
    ):
        config = dict(section.configuration or {})
        columns = list(config.get("columns", []))
        config["columns"] = [
            column for column in columns if column != "IMAGE_LINK"
        ] + ["IMAGE_LINK"]
        section.configuration = config
        section.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0006_add_inventory_image_link")]
    operations = [migrations.RunPython(move_image_link_last, migrations.RunPython.noop)]
