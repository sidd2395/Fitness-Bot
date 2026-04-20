import anthropic
from config import ANTHROPIC_API_KEY
from prompts import MORNING_SYSTEM_PROMPT, EVENING_SYSTEM_PROMPT

# Haiku for daily check-ins (fast, cheap), Sonnet reserved for weekly summary
DAILY_MODEL = "claude-haiku-4-5-20251001"

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def get_morning_coaching(user_prompt: str) -> str:
    """Calls Claude with the morning system prompt and returns coaching text."""
    message = client.messages.create(
        model=DAILY_MODEL,
        max_tokens=300,
        system=MORNING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


def get_evening_coaching(user_prompt: str) -> str:
    """Calls Claude with the evening system prompt and returns coaching text."""
    message = client.messages.create(
        model=DAILY_MODEL,
        max_tokens=300,
        system=EVENING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()
