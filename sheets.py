import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column indices (0-based) matching sheet layout:
# A=Date, B=Weight, C=Sleep, D=Training, E=Energy, F=Notes, G=Calories, H=Protein, I=Water, J=Streak
COL_DATE = 0
COL_WEIGHT = 1
COL_SLEEP = 2
COL_TRAINING = 3
COL_ENERGY = 4
COL_NOTES = 5
COL_CALORIES = 6
COL_PROTEIN = 7
COL_WATER = 8
COL_STREAK = 9


def _get_sheet():
    """Opens and returns the first worksheet."""
    creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEET_ID).sheet1


def format_date(dt: datetime) -> str:
    """Formats a datetime to 'D MMM YYYY' with no leading zero."""
    return dt.strftime("%-d %b %Y")


def today_str() -> str:
    return format_date(datetime.now())


def yesterday_str() -> str:
    return format_date(datetime.now() - timedelta(days=1))


def two_days_ago_str() -> str:
    return format_date(datetime.now() - timedelta(days=2))


def find_row_by_date(sheet, date_str: str):
    """
    Returns (row_index, row_values) if found, or (None, None) if not.
    row_index is 1-based (gspread convention).
    """
    all_values = sheet.get_all_values()
    for i, row in enumerate(all_values):
        if row and row[COL_DATE] == date_str:
            # Pad row to 10 columns so index access is always safe
            padded = row + [""] * (10 - len(row))
            return i + 1, padded
    return None, None


def get_all_rows(sheet):
    """Returns all rows as a list of padded lists, skipping header if present."""
    all_values = sheet.get_all_values()
    rows = []
    for row in all_values:
        if not row or row[COL_DATE] == "Date":
            continue
        rows.append(row + [""] * (10 - len(row)))
    return rows


def get_recent_history(sheet, exclude_date: str, limit: int = 4) -> list[str]:
    """
    Returns formatted history strings for the last `limit` days,
    excluding the current entry date (to avoid including today in context).
    """
    rows = get_all_rows(sheet)
    filtered = [r for r in rows if r[COL_DATE] != exclude_date]
    recent = filtered[-limit:]
    lines = []
    for r in recent:
        lines.append(
            f"{r[COL_DATE]} — Weight: {r[COL_WEIGHT]}kg, Sleep: {r[COL_SLEEP]}hrs, "
            f"Training: {r[COL_TRAINING]}, Energy: {r[COL_ENERGY]}/5"
        )
    return lines


def get_recent_evening_history(sheet, exclude_date: str, limit: int = 4) -> list[str]:
    """Evening history includes nutrition data."""
    rows = get_all_rows(sheet)
    filtered = [r for r in rows if r[COL_DATE] != exclude_date]
    recent = filtered[-limit:]
    lines = []
    for r in recent:
        lines.append(
            f"{r[COL_DATE]} — Training: {r[COL_TRAINING] or 'none'}, "
            f"Notes: {r[COL_NOTES] or 'none'}, "
            f"Calories: {r[COL_CALORIES] or 'not logged'}, "
            f"Protein: {r[COL_PROTEIN] or 'not logged'}g, "
            f"Water: {r[COL_WATER] or 'not logged'}L"
        )
    return lines


def log_morning(date_str: str, weight: str, sleep: str, training: str, energy: str, streak: int):
    """Appends a new morning row. Raises if entry already exists for that date."""
    sheet = _get_sheet()
    existing_idx, _ = find_row_by_date(sheet, date_str)
    if existing_idx is not None:
        raise ValueError(f"Morning entry already exists for {date_str}.")

    row = [""] * 10
    row[COL_DATE] = date_str
    row[COL_WEIGHT] = weight
    row[COL_SLEEP] = sleep
    row[COL_TRAINING] = training
    row[COL_ENERGY] = energy
    row[COL_STREAK] = str(streak)
    sheet.append_row(row, value_input_option="USER_ENTERED")


def update_evening(date_str: str, notes: str, calories: str, protein: str, water: str):
    """
    Updates evening columns on an existing row.
    If no row exists for that date, appends a new evening-only row.
    """
    sheet = _get_sheet()
    row_idx, existing = find_row_by_date(sheet, date_str)

    if row_idx is not None:
        # Update columns F-I on the existing row (1-based col = 0-based index + 1)
        sheet.update_cell(row_idx, COL_NOTES + 1, notes or "")
        sheet.update_cell(row_idx, COL_CALORIES + 1, calories or "")
        sheet.update_cell(row_idx, COL_PROTEIN + 1, protein or "")
        sheet.update_cell(row_idx, COL_WATER + 1, water or "")
    else:
        # No morning entry logged — create a row with evening data only
        row = [""] * 10
        row[COL_DATE] = date_str
        row[COL_NOTES] = notes or ""
        row[COL_CALORIES] = calories or ""
        row[COL_PROTEIN] = protein or ""
        row[COL_WATER] = water or ""
        sheet.append_row(row, value_input_option="USER_ENTERED")


def get_streak(prev_date_str: str) -> int:
    """
    Looks up the streak value from a previous row to calculate today's streak.
    Returns 0 if no previous row found (so new streak = 1).
    """
    sheet = _get_sheet()
    _, row = find_row_by_date(sheet, prev_date_str)
    if row is None:
        return 0
    try:
        return int(row[COL_STREAK]) if row[COL_STREAK] else 0
    except (ValueError, IndexError):
        return 0


def get_weight_delta(prev_date_str: str, current_weight: str) -> str:
    """Returns the weight delta vs the previous day, or '—' if no data."""
    sheet = _get_sheet()
    _, row = find_row_by_date(sheet, prev_date_str)
    if row is None or not row[COL_WEIGHT]:
        return "—"
    try:
        delta = float(current_weight) - float(row[COL_WEIGHT])
        return f"{delta:+.1f}"
    except ValueError:
        return "—"


def get_morning_context_for_evening(date_str: str) -> str:
    """Returns a formatted string of this morning's data, for the evening prompt."""
    sheet = _get_sheet()
    _, row = find_row_by_date(sheet, date_str)
    if row is None or not row[COL_WEIGHT]:
        return "No morning data logged today"
    return (
        f"Weight: {row[COL_WEIGHT]}kg, Sleep: {row[COL_SLEEP]}hrs, "
        f"Energy: {row[COL_ENERGY]}/5, Training: {row[COL_TRAINING]}"
    )
