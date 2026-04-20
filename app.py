import logging
import re
from flask import Flask, request, jsonify

import sheets
import ai
import bot
from prompts import HELP_TEXT, build_morning_user_prompt, build_evening_user_prompt

# Structured logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_morning(raw: str):
    """
    Parses 'weight, sleep, training, energy' from a morning message.
    Returns (weight, sleep, training, energy) or None if invalid.
    Training is free text so we only split on the first 3 commas.
    """
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 4:
        return None
    weight = parts[0]
    sleep = parts[1]
    energy = parts[-1]
    training = ", ".join(parts[2:-1])  # everything between sleep and energy
    if not all([weight, sleep, training, energy]):
        return None
    return weight, sleep, training, energy


def _parse_evening(raw: str):
    """
    Parses 'notes, calories, protein, water' from an evening message.
    Notes are required. Calories, protein, water are optional.
    Returns (notes, calories, protein, water) — optional fields may be empty string.
    """
    parts = [p.strip() for p in raw.split(",")]
    notes = parts[0] if parts else ""
    calories = parts[1] if len(parts) > 1 else ""
    protein = parts[2] if len(parts) > 2 else ""
    water = parts[3] if len(parts) > 3 else ""
    return notes, calories, protein, water


def _strip_prefix(text: str, prefix: str) -> str:
    """Removes prefix (e.g. 'e:', 'y:', 'ey:') and strips whitespace."""
    return re.sub(rf"^{re.escape(prefix)}\s*", "", text, flags=re.IGNORECASE).strip()


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

def handle_morning(raw_message: str, is_backdate: bool):
    """Processes a morning check-in (today or yesterday)."""
    parsed = _parse_morning(raw_message)
    if parsed is None:
        bot.send_message(
            "Couldn't parse that. Morning format: `weight, sleep, training, energy`\n"
            "Example: `98.5, 7, MT sparring, 4`"
        )
        return

    weight, sleep, training, energy = parsed

    if is_backdate:
        log_date = sheets.yesterday_str()
        streak_lookup_date = sheets.two_days_ago_str()
    else:
        log_date = sheets.today_str()
        streak_lookup_date = sheets.yesterday_str()

    # Streak and delta
    prev_streak = sheets.get_streak(streak_lookup_date)
    new_streak = prev_streak + 1
    weight_delta = sheets.get_weight_delta(streak_lookup_date, weight)

    # Write to sheet
    try:
        sheets.log_morning(log_date, weight, sleep, training, energy, new_streak)
    except ValueError:
        bot.send_message(f"Already have a morning entry for {log_date}. Use `y:` to backdate yesterday.")
        return

    # Build AI prompt and get coaching
    sheet = sheets._get_sheet()
    history = sheets.get_recent_history(sheet, exclude_date=log_date)
    user_prompt = build_morning_user_prompt(
        date=log_date,
        weight=weight,
        weight_delta=weight_delta,
        sleep=sleep,
        training=training,
        energy=energy,
        streak=new_streak,
        history_rows=history,
    )

    coaching = ai.get_morning_coaching(user_prompt)

    # Confirmation + coaching (split messages for clean UX)
    delta_display = f" ({weight_delta}kg)" if weight_delta != "—" else ""
    confirmation = (
        f"*Logged {log_date}*\n"
        f"Weight: {weight}kg{delta_display} | Sleep: {sleep}hrs | Energy: {energy}/5\n"
        f"Training: {training}\n"
        f"Streak: {new_streak} days"
    )
    bot.send_message(confirmation)
    bot.send_message(coaching)

    logger.info(f"Morning logged: date={log_date} weight={weight} streak={new_streak}")


def handle_evening(raw_message: str, is_backdate: bool):
    """Processes an evening check-in (today or yesterday)."""
    if not raw_message.strip():
        bot.send_message(
            "Couldn't parse that. Evening format: `e: notes, calories, protein, water`\n"
            "Example: `e: Good MT session, 1800, 160, 2.5`\nCalories, protein, water are optional."
        )
        return

    notes, calories, protein, water = _parse_evening(raw_message)

    if not notes:
        bot.send_message("Training notes are required. What did you do today?")
        return

    if is_backdate:
        log_date = sheets.yesterday_str()
    else:
        log_date = sheets.today_str()

    sheets.update_evening(log_date, notes, calories, protein, water)

    # Build AI prompt and get coaching
    sheet = sheets._get_sheet()
    morning_context = sheets.get_morning_context_for_evening(log_date)
    history = sheets.get_recent_evening_history(sheet, exclude_date=log_date)

    user_prompt = build_evening_user_prompt(
        date=log_date,
        training_notes=notes,
        calories=calories,
        protein=protein,
        water=water,
        morning_context=morning_context,
        history_rows=history,
    )

    coaching = ai.get_evening_coaching(user_prompt)

    # Confirmation + coaching
    cal_display = f"{calories} kcal" if calories else "not logged"
    protein_display = f"{protein}g" if protein else "not logged"
    water_display = f"{water}L" if water else "not logged"

    confirmation = (
        f"*Evening logged {log_date}*\n"
        f"Calories: {cal_display} | Protein: {protein_display} | Water: {water_display}\n"
        f"Notes: {notes}"
    )
    bot.send_message(confirmation)
    bot.send_message(coaching)

    logger.info(f"Evening logged: date={log_date}")


# ---------------------------------------------------------------------------
# Webhook route
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": True})

    message = data.get("message") or data.get("edited_message")
    if not message:
        return jsonify({"ok": True})

    text = message.get("text", "").strip()
    if not text:
        return jsonify({"ok": True})

    logger.info(f"Received message: {text[:80]}")

    try:
        # Help commands
        if text.lower() in ["/start", "/help"]:
            bot.send_message(HELP_TEXT)

        # Evening backdate: ey:
        elif re.match(r"^ey:", text, re.IGNORECASE):
            raw = _strip_prefix(text, "ey:")
            handle_evening(raw, is_backdate=True)

        # Morning backdate: y:
        elif re.match(r"^y:", text, re.IGNORECASE):
            raw = _strip_prefix(text, "y:")
            handle_morning(raw, is_backdate=True)

        # Evening: e:
        elif re.match(r"^e:", text, re.IGNORECASE):
            raw = _strip_prefix(text, "e:")
            handle_evening(raw, is_backdate=False)

        # Morning: no prefix
        else:
            handle_morning(text, is_backdate=False)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        bot.send_message("Something went wrong on my end. Try again in a moment.")

    return jsonify({"ok": True})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
