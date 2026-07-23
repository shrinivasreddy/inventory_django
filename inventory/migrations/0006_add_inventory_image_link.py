from django.db import migrations


def add_image_link(apps, schema_editor):
    InventorySection = apps.get_model("inventory", "InventorySection")
    TabRecord = apps.get_model("inventory", "TabRecord")
    for section in InventorySection.objects.filter(key__in=["sign", "pavement", "lane", "curb"]):
        config = dict(section.configuration or {})
        columns = list(config.get("columns", []))
        if "IMAGE_LINK" not in columns:
            columns.append("IMAGE_LINK")
        config["columns"] = columns
        config["text_fields"] = [f for f in config.get("text_fields", []) if f != "IMAGE_LINK"]
        auto_fields = list(config.get("auto_fields", []))
        if "IMAGE_LINK" not in auto_fields:
            auto_fields.append("IMAGE_LINK")
        config["auto_fields"] = auto_fields
        wide_cols = list(config.get("wide_cols", []))
        if "IMAGE_LINK" not in wide_cols:
            wide_cols.append("IMAGE_LINK")
        config["wide_cols"] = wide_cols
        section.configuration = config
        section.save(update_fields=["configuration"])

    for record in TabRecord.objects.filter(tab__in=["sign", "pavement", "lane", "curb"]):
        data = dict(record.data or {})
        data.setdefault("IMAGE_LINK", "")
        record.data = data
        record.save(update_fields=["data"])


def remove_image_link(apps, schema_editor):
    InventorySection = apps.get_model("inventory", "InventorySection")
    TabRecord = apps.get_model("inventory", "TabRecord")
    for section in InventorySection.objects.filter(key__in=["sign", "pavement", "lane", "curb"]):
        config = dict(section.configuration or {})
        for name in ("columns", "text_fields", "auto_fields", "wide_cols"):
            config[name] = [f for f in config.get(name, []) if f != "IMAGE_LINK"]
        section.configuration = config
        section.save(update_fields=["configuration"])
    for record in TabRecord.objects.filter(tab__in=["sign", "pavement", "lane", "curb"]):
        data = dict(record.data or {})
        data.pop("IMAGE_LINK", None)
        record.data = data
        record.save(update_fields=["data"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0005_alter_tabrecord_created_at")]
    operations = [migrations.RunPython(add_image_link, remove_image_link)]
