from copy import deepcopy

from django.db import migrations


def seed_database_configuration(apps, schema_editor):
    from inventory.seed_data import SPECS, TAB_ORDER

    InventorySection = apps.get_model("inventory", "InventorySection")
    DropdownOption = apps.get_model("inventory", "DropdownOption")
    AutoFillMapping = apps.get_model("inventory", "AutoFillMapping")
    MutcdMapping = apps.get_model("inventory", "MutcdMapping")
    MutcdClassification = apps.get_model("inventory", "MutcdClassification")
    MutcdFallback = apps.get_model("inventory", "MutcdFallback")
    TabState = apps.get_model("inventory", "TabState")

    for key in TAB_ORDER:
        seed_spec = deepcopy(SPECS[key])
        options = seed_spec.pop("default_options", {})
        mutcd_link = seed_spec.get("mutcd_link")
        mutcd_map = {}
        mutcd_classes = {}
        mutcd_fallbacks = {}
        if mutcd_link:
            mutcd_map = mutcd_link.pop("default_map", {})
            mutcd_classes = mutcd_link.pop("default_class", {})
            mutcd_fallbacks = mutcd_link.pop("default_word_fallback", {})
        auto_fill = seed_spec.get("auto_fill_map")
        type_map = auto_fill.pop("default_map", {}) if auto_fill else {}

        legacy = TabState.objects.filter(tab=key).first()
        if legacy:
            for field_name, values in legacy.options.items():
                merged = options.setdefault(field_name, [])
                for value in values:
                    if value not in merged:
                        merged.append(value)
            mutcd_map.update(legacy.mutcd_map)
            mutcd_classes.update(legacy.mutcd_to_class)
            mutcd_fallbacks.update(legacy.mutcd_word_fallback)
            type_map.update(legacy.type_map)

        section = InventorySection.objects.create(
            key=key,
            name=seed_spec["tab_label"],
            configuration=seed_spec,
        )

        option_rows = []
        for field_name, values in options.items():
            option_rows.extend(
                DropdownOption(
                    section=section,
                    field_name=field_name,
                    value=str(value),
                    sort_order=index,
                )
                for index, value in enumerate(values)
            )
        DropdownOption.objects.bulk_create(option_rows, ignore_conflicts=True)

        AutoFillMapping.objects.bulk_create(
            [
                AutoFillMapping(
                    section=section,
                    driver_value=str(driver_value),
                    values=values,
                )
                for driver_value, values in type_map.items()
            ],
            ignore_conflicts=True,
        )
        MutcdMapping.objects.bulk_create(
            [
                MutcdMapping(
                    section=section,
                    word_description=word,
                    mutcd_code=info.get("MUTCD", ""),
                    classification=info.get("MUTCD_CLASSIFICATION", ""),
                )
                for word, info in mutcd_map.items()
            ],
            ignore_conflicts=True,
        )
        MutcdClassification.objects.bulk_create(
            [
                MutcdClassification(
                    section=section,
                    code=code,
                    classification=classification,
                )
                for code, classification in mutcd_classes.items()
            ],
            ignore_conflicts=True,
        )
        MutcdFallback.objects.bulk_create(
            [
                MutcdFallback(
                    section=section,
                    code=code,
                    word_description=word,
                )
                for code, word in mutcd_fallbacks.items()
            ],
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_inventorysection_mutcdmapping_mutcdfallback_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_database_configuration, migrations.RunPython.noop),
    ]
