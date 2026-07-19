"""Seed data loader used only by the database migration/import command."""

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
