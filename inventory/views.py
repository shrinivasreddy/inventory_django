import io
import json
import threading
from datetime import date

from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from .models import TabRecord, TabState
from .specs import SPECS, TAB_ORDER, compute_auto_fields, missing_required_fields, build_reverse_map

# One lock per tab, held around every read-modify-write sequence, same
# rationale as the Flask version: with a single-process WSGI deployment
# (see README -- this remains a hard requirement), this prevents two
# concurrent requests from racing on ID generation or a renumber. Django's
# own transaction.atomic() gives us automatic rollback-on-exception on top
# of that, which the Flask/JSON-file version had to do by hand.
locks = {key: threading.Lock() for key in SPECS}


def parse_json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def get_tab_state(key):
    """Get-or-create the TabState row for this tab, seeded from the spec's
    defaults on first access -- the DB equivalent of the Flask version's
    load_json(path, default) fallback."""
    spec = SPECS[key]
    ts, created = TabState.objects.get_or_create(
        tab=key,
        defaults={
            "options": spec["default_options"],
            "mutcd_map": spec.get("mutcd_link", {}).get("default_map", {}),
            "mutcd_to_class": spec.get("mutcd_link", {}).get("default_class", {}),
            "mutcd_word_fallback": spec.get("mutcd_link", {}).get("default_word_fallback", {}),
            "type_map": spec.get("auto_fill_map", {}).get("default_map", {}),
        },
    )
    if created and spec.get("mutcd_link"):
        ts.mutcd_reverse_map = build_reverse_map(ts.mutcd_map, ts.mutcd_word_fallback)
        ts.save(update_fields=["mutcd_reverse_map"])
    return ts


def tab_state_as_dict(ts):
    return {
        "options": ts.options, "mutcd_map": ts.mutcd_map, "mutcd_to_class": ts.mutcd_to_class,
        "mutcd_word_fallback": ts.mutcd_word_fallback, "mutcd_reverse_map": ts.mutcd_reverse_map,
        "type_map": ts.type_map,
    }


def next_tab_id(key):
    from django.db.models import Max
    max_id = TabRecord.objects.filter(tab=key).aggregate(m=Max("tab_record_id"))["m"]
    return (max_id or 0) + 1


def renumber_tab_ids(key):
    """Ported from renumber_ids: re-sequence to 1..N after a delete. Safe to
    do as individual .save() calls in ascending order -- each target slot is
    always freed by the previous iteration before it's reused, so the
    (tab, tab_record_id) unique constraint is never violated mid-loop."""
    records = list(TabRecord.objects.filter(tab=key).order_by("tab_record_id"))
    for i, r in enumerate(records, start=1):
        if r.tab_record_id != i:
            r.tab_record_id = i
            r.save(update_fields=["tab_record_id"])


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def home(request):
    tabs = [{"key": k, "label": SPECS[k]["tab_label"]} for k in TAB_ORDER]
    return render(request, "index.html", {"tabs_json": json.dumps(tabs)})


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------
def api_spec(request, key):
    if key not in SPECS:
        return JsonResponse({"error": "Unknown tab"}, status=404)
    spec = SPECS[key]
    ts = get_tab_state(key)
    return JsonResponse({
        "key": key,
        "columns": spec["columns"],
        "dropdown_fields": spec["dropdown_fields"],
        "text_fields": spec["text_fields"],
        "auto_fields": spec["auto_fields"],
        "date_fields": spec["date_fields"],
        "uid_field": spec["uid_field"],
        "uid_prefix": spec["uid_prefix"],
        "uid_parts": spec["uid_parts"],
        "uid_required_msg": spec["uid_required_msg"],
        "preserve_case_fields": spec["preserve_case_fields"],
        "searchable_fields": spec.get("searchable_fields", []),
        "wide_cols": spec["wide_cols"],
        "sticky_fields": spec["sticky_fields"],
        "banner_title": spec["banner_title"],
        "banner_subtitle": spec["banner_subtitle"],
        "options": ts.options,
        "mutcd_map": ts.mutcd_map,
        "mutcd_to_class": ts.mutcd_to_class,
        "mutcd_reverse_map": ts.mutcd_reverse_map,
        "auto_fill_map": spec.get("auto_fill_map"),
        "type_map": ts.type_map,
        "conditional_dropdowns": spec.get("conditional_dropdowns", {}),
        "default_field_values": spec.get("default_field_values", {}),
    })


# ---------------------------------------------------------------------------
# Records: GET (list) / POST (add) / DELETE (delete-all)
# ---------------------------------------------------------------------------
@csrf_exempt
def api_records(request, key):
    if key not in SPECS:
        return JsonResponse({"error": "Unknown tab"}, status=404)
    spec = SPECS[key]

    if request.method == "GET":
        with locks[key]:
            qs = TabRecord.objects.filter(tab=key).order_by("tab_record_id")
            records = [r.as_row() for r in qs]
            nid = next_tab_id(key)
        return JsonResponse({"records": records, "next_id": nid})

    if request.method == "POST":
        body = parse_json_body(request)
        raw_row = body.get("row")
        if not isinstance(raw_row, dict):
            return JsonResponse({"error": "Malformed request: 'row' must be an object."}, status=400)
        row = {c: str(raw_row.get(c, "") or "") for c in spec["columns"]}
        row.pop("ID", None)

        with locks[key]:
            ts_dict = tab_state_as_dict(get_tab_state(key))
            row = compute_auto_fields(key, row, ts_dict)
            missing = missing_required_fields(key, row)
            if missing:
                return JsonResponse({"error": spec["uid_required_msg"]}, status=400)
            try:
                with transaction.atomic():
                    new_id = next_tab_id(key)
                    rec = TabRecord.objects.create(tab=key, tab_record_id=new_id, data=row)
            except Exception:
                return JsonResponse({"error": "Failed to save the record to the database."}, status=500)
            return JsonResponse({"record": rec.as_row(), "next_id": next_tab_id(key)})

    if request.method == "DELETE":
        with locks[key]:
            try:
                with transaction.atomic():
                    TabRecord.objects.filter(tab=key).delete()
            except Exception:
                return JsonResponse({"error": "Failed to clear records."}, status=500)
        return JsonResponse({"ok": True, "next_id": 1})

    return HttpResponseNotAllowed(["GET", "POST", "DELETE"])


# ---------------------------------------------------------------------------
# Single record: PUT (update) / DELETE
# ---------------------------------------------------------------------------
@csrf_exempt
def api_record_detail(request, key, rec_id):
    if key not in SPECS:
        return JsonResponse({"error": "Unknown tab"}, status=404)
    spec = SPECS[key]

    if request.method == "PUT":
        body = parse_json_body(request)
        raw_row = body.get("row")
        if not isinstance(raw_row, dict):
            return JsonResponse({"error": "Malformed request: 'row' must be an object."}, status=400)
        row = {c: str(raw_row.get(c, "") or "") for c in spec["columns"]}
        row.pop("ID", None)

        with locks[key]:
            try:
                rec = TabRecord.objects.get(tab=key, tab_record_id=rec_id)
            except TabRecord.DoesNotExist:
                return JsonResponse({"error": "Record not found"}, status=404)

            ts_dict = tab_state_as_dict(get_tab_state(key))
            row = compute_auto_fields(key, row, ts_dict)
            missing = missing_required_fields(key, row)
            if missing:
                return JsonResponse({"error": spec["uid_required_msg"]}, status=400)

            try:
                with transaction.atomic():
                    rec.data = row
                    rec.save(update_fields=["data", "updated_at"])
            except Exception:
                return JsonResponse({"error": "Failed to save the record to the database."}, status=500)
            return JsonResponse({"record": rec.as_row()})

    if request.method == "DELETE":
        with locks[key]:
            try:
                rec = TabRecord.objects.get(tab=key, tab_record_id=rec_id)
            except TabRecord.DoesNotExist:
                return JsonResponse({"error": "Record not found"}, status=404)
            try:
                with transaction.atomic():
                    rec.delete()
                    renumber_tab_ids(key)
            except Exception:
                return JsonResponse({"error": "Failed to delete the record."}, status=500)
            return JsonResponse({"ok": True, "next_id": next_tab_id(key)})

    return HttpResponseNotAllowed(["PUT", "DELETE"])


# ---------------------------------------------------------------------------
# Dropdown "+" add option
# ---------------------------------------------------------------------------
@csrf_exempt
def api_options(request, key):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if key not in SPECS:
        return JsonResponse({"error": "Unknown tab"}, status=404)
    spec = SPECS[key]

    data = parse_json_body(request)
    field = data.get("field")
    value = str(data.get("value") or "").strip()
    if not field or not isinstance(field, str) or field not in spec["columns"]:
        return JsonResponse({"error": "A valid field name is required."}, status=400)
    if not value:
        return JsonResponse({"error": "value is required"}, status=400)
    if field not in spec["preserve_case_fields"]:
        value = value.upper()

    with locks[key]:
        ts = get_tab_state(key)
        opts = ts.options.setdefault(field, [])
        if value not in opts:
            opts.append(value)
            ts.save(update_fields=["options"])

        result = {"field": field, "value": value, "options": ts.options[field]}

        ml = spec.get("mutcd_link")
        if ml and field == ml["code_field"] and value not in ts.mutcd_to_class:
            classification = str(data.get("classification") or "").strip()
            ts.mutcd_to_class[value] = classification
            ts.save(update_fields=["mutcd_to_class"])
            result["mutcd_to_class_entry"] = {"code": value, "classification": classification}

        elif ml and field == ml["word_field"] and value not in ts.mutcd_map:
            mutcd_code = str(data.get("mutcd_code") or "").strip()
            classification = ts.mutcd_to_class.get(mutcd_code, "")
            if mutcd_code and not classification:
                classification = str(data.get("classification") or "").strip()
                if classification:
                    ts.mutcd_to_class[mutcd_code] = classification
                    ts.save(update_fields=["mutcd_to_class"])
            ts.mutcd_map[value] = {"MUTCD": mutcd_code, "MUTCD_CLASSIFICATION": classification}
            ts.mutcd_reverse_map = build_reverse_map(ts.mutcd_map, ts.mutcd_word_fallback)
            ts.save(update_fields=["mutcd_map", "mutcd_reverse_map"])
            result["mutcd_map_entry"] = {"word": value, **ts.mutcd_map[value]}
            result["mutcd_reverse_map"] = ts.mutcd_reverse_map

        afm = spec.get("auto_fill_map")
        if afm and field == afm["driver_field"] and value not in ts.type_map:
            entry = {}
            for dep_field in afm["dependent_fields"]:
                entry[dep_field] = str(data.get(f"dep_{dep_field}") or "").strip()
            ts.type_map[value] = entry
            ts.save(update_fields=["type_map"])
            result["type_map_entry"] = {"driver_value": value, "fields": entry}

    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------
def write_sheet(key, ws, records):
    spec = SPECS[key]
    columns = spec["columns"]

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")

    ws.append(columns)
    for col_idx, _ in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    def is_number_like(val):
        if val is None:
            return True
        s = str(val).strip()
        if s == "":
            return True
        try:
            float(s)
            return True
        except ValueError:
            return False

    numeric_fields = set(spec.get("extra_numeric_fields", []))
    numeric_fields |= {c for c in columns if "LATITUDE" in c or "LONGITUDE" in c}
    for c in columns:
        if c in numeric_fields:
            continue
        has_value = any(str(row.get(c, "")).strip() != "" for row in records)
        if has_value and all(is_number_like(row.get(c)) for row in records):
            numeric_fields.add(c)

    for row in records:
        values = []
        for c in columns:
            val = row.get(c, "")
            if c in numeric_fields and val not in (None, ""):
                try:
                    fval = float(val)
                    val = int(fval) if fval.is_integer() else fval
                except (TypeError, ValueError):
                    pass
            values.append(val)
        ws.append(values)

    for col_idx, col_name in enumerate(columns, start=1):
        max_len = len(col_name)
        for row in records:
            val = str(row.get(col_name, ""))
            max_len = max(max_len, len(val))
        ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 4

    ws.freeze_panes = "A2"


def _xlsx_response(wb, filename):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def api_export(request, key):
    if key not in SPECS:
        return JsonResponse({"error": "Unknown tab"}, status=404)
    spec = SPECS[key]
    with locks[key]:
        records = [r.as_row() for r in TabRecord.objects.filter(tab=key).order_by("tab_record_id")]
    if not records:
        return JsonResponse({"error": "There are no records to export yet."}, status=400)

    wb = Workbook()
    ws = wb.active
    ws.title = spec["export_sheet_name"]
    write_sheet(key, ws, records)

    filename = f"{spec['export_filename_prefix']}_{date.today().isoformat()}.xlsx"
    return _xlsx_response(wb, filename)


def api_export_all(request):
    snapshots = {}
    for key in TAB_ORDER:
        with locks[key]:
            snapshots[key] = [r.as_row() for r in TabRecord.objects.filter(tab=key).order_by("tab_record_id")]

    wb = Workbook()
    wb.remove(wb.active)
    any_data = False
    for key in TAB_ORDER:
        if not snapshots[key]:
            continue
        any_data = True
        ws = wb.create_sheet(title=SPECS[key]["export_sheet_name"])
        write_sheet(key, ws, snapshots[key])
    if not any_data:
        return JsonResponse({"error": "There are no records in any tab to export yet."}, status=400)

    filename = f"All_Inventories_{date.today().isoformat()}.xlsx"
    return _xlsx_response(wb, filename)
