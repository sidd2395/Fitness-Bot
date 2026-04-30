# Fitness Bot — Personal AI Coaching via Telegram

A personal fitness tracking bot built on Telegram and powered by Claude (Haiku). Logs daily check-ins to Google Sheets and responds with coaching from Coach Reyes, an AI persona calibrated to give direct, data-driven feedback rather than generic motivation.

Built for personal use and as a portfolio piece demonstrating prompt architecture, automation, and AI product thinking.

**Live and in daily use.**

---

## What It Does

You send a structured message to your Telegram bot. It logs your data to Google Sheets and Coach Reyes responds with a personalised coaching message based on your numbers and recent history.

Two check-ins per day:

**Morning:** weight, sleep hours, planned training, energy level. Coach Reyes reads your last 4 days of data and tells you what today's numbers actually mean, whether sleep is hurting your recovery, and gives you one clear instruction for the day.

**Evening:** training notes, calories, protein, water. Coach Reyes debriefs the day, calls out any nutrition gaps directly, and sets up tomorrow.

Both support backdating (yesterday's entries) so a missed log doesn't break the flow.

---

## Product Decisions Worth Noting

**Why Haiku and not Sonnet?**
Daily check-ins are short, structured, and context-rich. Haiku handles them well at a fraction of the cost. Sonnet is reserved for the weekly summary (not yet built) where deeper pattern analysis earns the extra cost.

**Why a 4-day history window?**
Enough context for Coach Reyes to spot short-term patterns (two poor sleep nights in a row, nutrition collapsing mid-week) without diluting the prompt with stale data. A rolling 7-day window made responses too retrospective.

**Why prose responses instead of structured output?**
The bot is used daily. Bullet points and headers feel clinical and get ignored. Prose that reads like a coach talking feels like feedback worth acting on. Response length is capped at 60-120 words to keep it punchy.

**Why Google Sheets and not a database?**
Zero setup cost, instant visibility, easy to inspect and manually correct if something goes wrong. For a personal tool with one user, a database adds complexity without adding value.

**Why a streak counter?**
Streaks are a psychological lever for momentum-driven users. Knowing the number creates a small daily commitment device. The streak resets on a missed day intentionally, consecutive consistency is the metric that matters.

---

## Tech Stack

- Python 3.11
- Flask (webhook receiver)
- gunicorn (production WSGI server)
- Anthropic API (claude-haiku-4-5)
- gspread + google-auth (Google Sheets read/write)
- Telegram Bot API (webhook mode)
- Railway (hosting, auto-deploys on push)

---

## Architecture

Six files, each with one job:

| File | Responsibility |
|------|---------------|
| `app.py` | Flask webhook handler, message routing, orchestration |
| `sheets.py` | All Google Sheets reads and writes |
| `ai.py` | Claude API calls, morning and evening |
| `bot.py` | Telegram message sender |
| `config.py` | Environment variable loader |
| `prompts.py` | System prompts and user prompt builders |

No business logic in route handlers. No database calls in routes. All sheet operations go through `sheets.py`, all AI calls go through `ai.py`.

---

## Message Formats

```
Morning:         98.5, 7, MT sparring, 4
Evening:         e: Good session, upper body focused, 1850, 165, 2.5
Backdate AM:     y: 98.5, 6, gym, 3
Backdate PM:     ey: Rest day, 1900, 150, 2.0
Help:            /help
```

Fields: weight (kg), sleep (hrs), training (free text), energy (1-5), training notes, calories, protein (g), water (L). Evening nutrition fields are optional but Coach Reyes calls it out if missing.

---

## Google Sheet Structure

| A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| Date | Weight | Sleep | Training | Energy | Notes | Calories | Protein | Water | Streak |

---

## Running Locally

```bash
git clone https://github.com/sidd2395/Fitness-Bot.git
cd Fitness-Bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your credentials
python3 app.py
```

Required environment variables (see `.env.example`):

```
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
ANTHROPIC_API_KEY
GOOGLE_SHEET_ID
GOOGLE_SHEETS_CREDENTIALS
```

`GOOGLE_SHEETS_CREDENTIALS` is the full service account JSON as a single-line string.

---

## Deploying to Railway

1. Push to GitHub
2. Create new Railway project, deploy from this repo
3. Add all environment variables in the Railway Variables tab
4. Generate a Railway domain in Settings
5. Register the Telegram webhook:

```bash
curl "https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://your-railway-url.up.railway.app/webhook"
```

Railway auto-deploys on every push to main.

---

## What Is Not Yet Built

- Scheduled morning reminder (8am SGT)
- Nudge if no morning entry by 10am
- Evening reminder if training was not a rest day
- Weekly summary (Sunday, Claude Sonnet, richer pattern analysis)
- Multi-user support
