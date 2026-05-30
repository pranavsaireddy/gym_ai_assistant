# backend/app/agents/perception.py
"""
Perception Agent
================
First thing that runs on every message.
Classifies: intent category, emotional tone, urgency level.
Returns a structured dict — no LLM response text, just signals.

Uses a single fast Groq call at temperature=0 (deterministic).
Output feeds directly into the planner to decide the action plan.
"""
import logging
import json
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)
client = Groq(api_key=settings.GROQ_API_KEY)

PERCEPTION_PROMPT = """You are a perception module for a gym AI assistant.
Analyze the member's message and return ONLY a JSON object — no explanation, no markdown.

Categories:
  ATTENDANCE   - visits, check-ins, streaks, how often they came
  MEMBERSHIP   - expiry, renewal, plan details, billing, payments
  DIET         - food, nutrition, what to eat, supplements, meals
  FITNESS      - exercises, workouts, muscle, fat loss, training advice
  OCCUPANCY    - how busy is the gym, how many people, best time to come
  ANALYTICS    - gym-wide stats (only valid for owner/staff role)
  GENERAL      - greetings, gym hours, policies, anything else

Mood signals:
  positive     - excited, happy, motivated, celebrating ("I lost 2kg!", "my streak is great")
  frustrated   - annoyed, complaining, giving up ("this isn't working", "so tired", "useless")
  disengaged   - brief, low energy, minimal effort ("ok", "fine", "whatever", "k")
  unknown      - neutral or unclear

Urgency:
  high    - membership expiring mention, urgent question, distress
  normal  - regular question or update

Return exactly this JSON:
{
  "category": "ATTENDANCE",
  "mood": "positive",
  "urgency": "normal",
  "is_question": true,
  "key_topic": "monthly visits"
}"""


def run_perception(user_message: str, role: str = "member") -> dict:
    """
    Classify a user message.

    Args:
        user_message: Raw text from the member
        role: 'member' | 'owner' | 'staff' — affects ANALYTICS routing

    Returns:
        {category, mood, urgency, is_question, key_topic}
    """
    # Shortcut for very short messages (greetings, one-word replies)
    stripped = user_message.strip().lower()
    if stripped in {"hi", "hello", "hey", "hii", "helo", "sup", "yo"}:
        return {
            "category":   "GENERAL",
            "mood":       "positive",
            "urgency":    "normal",
            "is_question": False,
            "key_topic":  "greeting",
        }

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": PERCEPTION_PROMPT},
                {"role": "user",   "content": user_message[:500]},
            ],
            max_tokens=80,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        # Validate category
        valid_categories = {
            "ATTENDANCE", "MEMBERSHIP", "DIET", "FITNESS",
            "OCCUPANCY", "ANALYTICS", "GENERAL",
        }
        if result.get("category") not in valid_categories:
            result["category"] = "GENERAL"

        # Block ANALYTICS for non-staff
        if result.get("category") == "ANALYTICS" and role == "member":
            result["category"] = "GENERAL"

        return result

    except Exception as e:
        logger.warning(f"Perception agent failed: {e} — defaulting to GENERAL")
        return {
            "category":    "GENERAL",
            "mood":        "unknown",
            "urgency":     "normal",
            "is_question": True,
            "key_topic":   "general",
        }