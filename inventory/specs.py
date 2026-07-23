"""Database-backed inventory section specifications and business logic."""

from copy import deepcopy

from .models import (
    AutoFillMapping,
    DropdownOption,
    InventorySection,
    MutcdClassification,
    MutcdFallback,
    MutcdMapping,
)

TAB_ORDER = ["sign", "pavement", "lane", "curb"]


def get_spec(key):
    config = deepcopy(InventorySection.objects.get(key=key).configuration)
    # IMAGE_LINK is a platform field, not optional administrator configuration.
    # Keep older/restored databases compatible even if their saved section JSON
    # predates the image-upload migration.
    columns = config.setdefault("columns", [])
    config["columns"] = [field for field in columns if field != "IMAGE_LINK"] + ["IMAGE_LINK"]
    config["text_fields"] = [
        field for field in config.setdefault("text_fields", []) if field != "IMAGE_LINK"
    ]
    auto_fields = config.setdefault("auto_fields", [])
    if "IMAGE_LINK" not in auto_fields:
        auto_fields.append("IMAGE_LINK")
    wide_cols = config.setdefault("wide_cols", [])
    if "IMAGE_LINK" not in wide_cols:
        wide_cols.append("IMAGE_LINK")
    return config


def get_all_specs():
    sections = InventorySection.objects.in_bulk(TAB_ORDER, field_name="key")
    return {key: get_spec(key) for key in TAB_ORDER if key in sections}


def get_section_state(key):
    spec = get_spec(key)
    options = {}
    for option in DropdownOption.objects.filter(section_id=key).order_by("field_name", "sort_order", "id"):
        options.setdefault(option.field_name, []).append(option.value)
    mutcd_rows = list(MutcdMapping.objects.filter(section_id=key))
    mutcd_map = {
        row.word_description: {
            "MUTCD": row.mutcd_code,
            "MUTCD_CLASSIFICATION": row.classification,
        }
        for row in mutcd_rows
    }
    mutcd_to_class = {
        row.code: row.classification
        for row in MutcdClassification.objects.filter(section_id=key)
    }
    # MUTCD mappings are themselves editable reference data. Keep their code
    # and description visible in the corresponding dropdowns even when an
    # administrator creates the mapping directly rather than separately
    # creating two DropdownOption rows.
    mutcd_link = spec.get("mutcd_link")
    if mutcd_link:
        word_options = options.setdefault(mutcd_link["word_field"], [])
        code_options = options.setdefault(mutcd_link["code_field"], [])
        for row in mutcd_rows:
            if row.word_description and row.word_description not in word_options:
                word_options.append(row.word_description)
            if row.mutcd_code and row.mutcd_code not in code_options:
                code_options.append(row.mutcd_code)
            if row.mutcd_code and row.classification:
                mutcd_to_class.setdefault(row.mutcd_code, row.classification)
    mutcd_word_fallback = {
        row.code: row.word_description
        for row in MutcdFallback.objects.filter(section_id=key)
    }
    type_map = {
        row.driver_value: row.values
        for row in AutoFillMapping.objects.filter(section_id=key)
    }
    for values in options.values():
        values.sort(key=lambda value: str(value).casefold())
    mutcd_word_options = build_word_options(mutcd_map, mutcd_word_fallback)
    return {
        "options": options,
        "mutcd_map": mutcd_map,
        "mutcd_to_class": mutcd_to_class,
        "mutcd_word_fallback": mutcd_word_fallback,
        "mutcd_word_options": mutcd_word_options,
        "mutcd_reverse_map": {
            code: words[0] for code, words in mutcd_word_options.items() if words
        },
        "type_map": type_map,
    }


def build_word_options(mutcd_map, mutcd_word_fallback):
    """Return every selectable word description grouped by MUTCD code."""
    options = {}
    for word, info in mutcd_map.items():
        code = info.get("MUTCD", "")
        if code:
            options.setdefault(code, []).append(word)
    # A fallback remains useful only when no explicit mapping exists.
    for code, word in mutcd_word_fallback.items():
        if code and word and code not in options:
            options[code] = [word]
    for words in options.values():
        words.sort(key=str.casefold)
    return options


def compute_auto_fields(key, row, tab_state):
    spec = get_spec(key)
    parts = [str(row.get(f, "")).strip() for f in spec["uid_parts"]]
    row[spec["uid_field"]] = spec["uid_prefix"] + "_" + "_".join(parts) if all(parts) else ""

    if spec.get("mutcd_link"):
        ml = spec["mutcd_link"]
        mutcd_code = str(row.get(ml["code_field"], "")).strip()
        word_desc = str(row.get(ml["word_field"], "")).strip()
        if word_desc and word_desc in tab_state["mutcd_map"]:
            classification = tab_state["mutcd_map"][word_desc].get("MUTCD_CLASSIFICATION", "")
        elif mutcd_code and mutcd_code in tab_state["mutcd_to_class"]:
            classification = tab_state["mutcd_to_class"][mutcd_code]
        else:
            classification = ""
        row[ml["class_field"]] = classification

    afm = spec.get("auto_fill_map")
    if afm:
        driver_val = str(row.get(afm["driver_field"], "")).strip()
        mapped = tab_state["type_map"].get(driver_val, {})
        cond = spec.get("conditional_dropdowns", {})
        for dep_field in afm["dependent_fields"]:
            trigger = cond.get(dep_field)
            if trigger and driver_val in trigger["trigger_values"]:
                submitted = str(row.get(dep_field, "")).strip()
                options = trigger["options"]
                if submitted not in options:
                    default_val = mapped.get(dep_field, "")
                    submitted = default_val if default_val in options else (options[0] if options else "")
                row[dep_field] = submitted
            else:
                row[dep_field] = mapped.get(dep_field, "")
    if "LEVEL(R)" in spec["auto_fields"]:
        row["LEVEL(R)"] = "R"
    return row


def missing_required_fields(key, row):
    return [f for f in get_spec(key)["uid_parts"] if not str(row.get(f, "")).strip()]
