"""Security helpers shared by Excel import and export paths."""


def safe_excel_cell(value):
    """Prevent user-controlled strings from becoming formulas in Excel."""
    if isinstance(value, str) and value.startswith(("=", "\t", "\r", "\n")):
        return "'" + value
    return value
