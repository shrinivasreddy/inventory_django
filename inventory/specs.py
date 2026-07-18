"""
Tab specs (Sign / Pavement / Lane / Curb) and the auto-field computation
logic. This is the same business logic from the Flask version, unchanged --
it's pure functions over plain dicts, so it doesn't care which web
framework or storage layer sits around it. Only the storage layer
(models.py) and the routing layer (views.py) are Django-specific.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_seed(name):
    with open(os.path.join(DATA_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


SIGN_SPEC = {
    "key": "sign",
    "banner_title": "Sign Inventory Data Entry",
    "banner_subtitle": "Roadway Sign Asset Management",
    "tab_label": "Sign Inventory",
    "columns": load_seed("COLUMNS"),
    "dropdown_fields": load_seed("DROPDOWN_FIELDS"),
    "text_fields": load_seed("TEXT_FIELDS") + ["LEVEL(R)"],  # manual entry, not auto-computed
    "auto_fields": [f for f in load_seed("AUTO_FIELDS") if f != "LEVEL(R)"],
    "default_options": load_seed("DEFAULT_OPTIONS"),
    "date_fields": ["INSP_DATE"],
    "uid_field": "SIGN_UID",
    "uid_prefix": "SR",
    "uid_parts": ["ST_ID", "POLE_ID", "SIGN"],
    "uid_required_msg": "ST_ID, POLE_ID, and SIGN are required to generate SIGN_UID.",
    "preserve_case_fields": ["MUTCD"],
    "searchable_fields": ["MUTCD", "WORD_DESCRIPTION"],
    "wide_cols": ["STREET_NAME", "SIGN_UID", "WORD_DESCRIPTION"],
    "sticky_fields": ["ST_ID", "STREET_NAME"],
    "export_sheet_name": "Sign Inventory",
    "export_filename_prefix": "Sign_Inventory",
    "mutcd_link": {
        "word_field": "WORD_DESCRIPTION", "code_field": "MUTCD", "class_field": "MUTCD_CLASSIFICATION",
        "default_map": load_seed("DEFAULT_MUTCD_MAP"),
        "default_class": load_seed("MUTCD_TO_CLASS"),
        "default_word_fallback": load_seed("MUTCD_WORD_FALLBACK"),
    },
}

PAVEMENT_SPEC = {
    "key": "pavement",
    "banner_title": "Pavement Marking Inventory Data Entry",
    "banner_subtitle": "Pavement Marking Asset Management",
    "tab_label": "Pavement Inventory",
    "columns": load_seed("PAVEMENT_COLUMNS"),
    "dropdown_fields": load_seed("PAVEMENT_DROPDOWN_FIELDS"),
    "text_fields": load_seed("PAVEMENT_TEXT_FIELDS"),
    "auto_fields": load_seed("PAVEMENT_AUTO_FIELDS"),
    "default_options": load_seed("PAVEMENT_DEFAULT_OPTIONS"),
    "date_fields": ["INSP_DATE"],
    "uid_field": "PM_UID",
    "uid_prefix": "PM",
    "uid_parts": ["ST_ID", "PM_ID"],
    "uid_required_msg": "ST_ID and PM_ID are required to generate PM_UID.",
    "preserve_case_fields": [],
    "wide_cols": ["STREET_NAME", "MUTCD", "PAVEMENT_MARKING_TYPE", "IMAGE_LINK", "PM_UID"],
    "sticky_fields": ["ST_ID", "STREET_NAME"],
    "export_sheet_name": "Pavement Inventory",
    "export_filename_prefix": "Pavement_Inventory",
    "auto_fill_map": {
        "driver_field": "PAVEMENT_MARKING_TYPE",
        "dependent_fields": ["MUTCD", "MATERIAL", "ON_ROADWAY"],
        "default_map": load_seed("PAVEMENT_TYPE_MAP"),
        "prompt_labels": {
            "MUTCD": "MUTCD category for", "MATERIAL": "MATERIAL for", "ON_ROADWAY": "ON_ROADWAY (YES/NO) for",
        },
    },
}

LANE_SPEC = {
    "key": "lane",
    "banner_title": "Lane Inventory Data Entry",
    "banner_subtitle": "Lane Marking Asset Management",
    "tab_label": "Lane Inventory",
    "columns": load_seed("LANE_COLUMNS"),
    "dropdown_fields": load_seed("LANE_DROPDOWN_FIELDS"),
    "text_fields": load_seed("LANE_TEXT_FIELDS"),
    "auto_fields": load_seed("LANE_AUTO_FIELDS"),
    "default_options": load_seed("LANE_DEFAULT_OPTIONS"),
    "date_fields": [],
    "uid_field": "LANE_UID",
    "uid_prefix": "LM",
    "uid_parts": ["ST_ID", "LM_ID"],
    "uid_required_msg": "ST_ID and LM_ID are required to generate LANE_UID.",
    "preserve_case_fields": [],
    "extra_numeric_fields": ["LENGTH_FT"],
    "wide_cols": ["STREET_NAME", "PAVEMENT_MARKING_TYPE", "IMAGE_LINK", "LANE_UID"],
    "sticky_fields": ["ST_ID", "STREET_NAME"],
    "export_sheet_name": "Lane Inventory",
    "export_filename_prefix": "Lane_Inventory",
    "auto_fill_map": {
        "driver_field": "PAVEMENT_MARKING_TYPE",
        "dependent_fields": ["COLOR", "MUTCD", "MATERIAL", "ON_ROADWAY"],
        "default_map": load_seed("LANE_TYPE_MAP"),
        "prompt_labels": {
            "COLOR": "COLOR for", "MUTCD": "MUTCD category for",
            "MATERIAL": "MATERIAL for", "ON_ROADWAY": "ON_ROADWAY (YES/NO) for",
        },
    },
    "conditional_dropdowns": {
        "MUTCD": {"trigger_values": ["27B"], "options": ["RIGHT EDGE LANE", "LEFT EDGE LANE"]},
    },
}

CURB_SPEC = {
    "key": "curb",
    "banner_title": "Curb Inventory Data Entry",
    "banner_subtitle": "Curb Marking Asset Management",
    "tab_label": "Curb Inventory",
    "columns": load_seed("CURB_COLUMNS"),
    "dropdown_fields": load_seed("CURB_DROPDOWN_FIELDS"),
    "text_fields": load_seed("CURB_TEXT_FIELDS"),
    "auto_fields": load_seed("CURB_AUTO_FIELDS"),
    "default_options": load_seed("CURB_DEFAULT_OPTIONS"),
    "date_fields": ["INSP_DT"],
    "uid_field": "CURB_UID",
    "uid_prefix": "CM",
    "uid_parts": ["ST_ID", "CM_ID"],
    "uid_required_msg": "ST_ID and CM_ID are required to generate CURB_UID.",
    "preserve_case_fields": [],
    "extra_numeric_fields": ["LENGTH_FT"],
    "default_field_values": {"MATERIAL": "PAINT"},
    "wide_cols": ["STREET_NAME", "CURB_MARKING", "IMAGE_LINK", "CURB_UID"],
    "sticky_fields": ["ST_ID", "STREET_NAME"],
    "export_sheet_name": "Curb Inventory",
    "export_filename_prefix": "Curb_Inventory",
    "auto_fill_map": {
        "driver_field": "CURB_MARKING",
        "dependent_fields": ["ON_ROADWAY"],
        "default_map": load_seed("CURB_TYPE_MAP"),
        "prompt_labels": {"ON_ROADWAY": "ON_ROADWAY (YES/NO) for"},
    },
}

SPECS = {"sign": SIGN_SPEC, "pavement": PAVEMENT_SPEC, "lane": LANE_SPEC, "curb": CURB_SPEC}
TAB_ORDER = ["sign", "pavement", "lane", "curb"]


def build_reverse_map(mutcd_map, mutcd_word_fallback):
    reverse_map = dict(mutcd_word_fallback)
    seen = set()
    for word, info in mutcd_map.items():
        code = info.get("MUTCD", "")
        if code and code not in seen:
            reverse_map[code] = word
            seen.add(code)
    return reverse_map


def compute_auto_fields(key, row, tab_state):
    """Ported from _refresh_auto_fields / _collect_row. `tab_state` is a
    dict with options/mutcd_map/mutcd_to_class/type_map for this tab (see
    views.tab_state_as_dict) -- always recomputed server-side; the client's
    live preview is a UX convenience only, never trusted as the source of
    truth."""
    spec = SPECS[key]

    parts = [str(row.get(f, "")).strip() for f in spec["uid_parts"]]
    row[spec["uid_field"]] = spec["uid_prefix"] + "_" + "_".join(parts) if all(parts) else ""

    if spec.get("mutcd_link"):
        ml = spec["mutcd_link"]
        mutcd_code = str(row.get(ml["code_field"], "")).strip()
        word_desc = str(row.get(ml["word_field"], "")).strip()
        if mutcd_code and mutcd_code in tab_state["mutcd_to_class"]:
            classification = tab_state["mutcd_to_class"][mutcd_code]
        elif word_desc and word_desc in tab_state["mutcd_map"]:
            classification = tab_state["mutcd_map"][word_desc].get("MUTCD_CLASSIFICATION", "")
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

    # Generic hook retained for any future tab that wants a truly constant
    # auto field; not used by any current tab (Sign's LEVEL(R) is now manual).
    if "LEVEL(R)" in spec["auto_fields"]:
        row["LEVEL(R)"] = "R"

    return row


def missing_required_fields(key, row):
    return [f for f in SPECS[key]["uid_parts"] if not str(row.get(f, "")).strip()]
