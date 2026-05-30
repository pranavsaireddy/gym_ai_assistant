# backend/app/agents/diet.py
"""
Diet & Fitness Agent
====================
No DB queries. Uses LLM knowledge + owner-editable diet_guidelines.txt.
Returns structured output including the advice text.
"""
import logging
from pathlib import Path
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)
client = Groq(api_key=settings.GROQ_API_KEY)

_GUIDELINES_PATH = Path(__file__).parent / "diet_guidelines.txt"

BASE_SYSTEM = """You are a knowledgeable fitness and nutrition coach at Muscletech Fitness gym in Hyderabad, India.
Give practical, science-based advice on nutrition, diet, supplements, and exercise.
Keep answers focused and practical — suited to Indian dietary habits and lifestyle.
Always recommend consulting a doctor for medical conditions.
Never recommend dangerous supplements or extreme diets.
Return your advice as plain text — no bullet points unless specifically asked."""


def _load_guidelines() -> str:
    if _GUIDELINES_PATH.exists():
        content = _GUIDELINES_PATH.read_text(encoding="utf-8").strip()
        return f"\n\nGym-specific guidelines (follow these above general advice):\n{content}"
    return ""


def run_diet(
    query: str,
    member_context: dict | None = None,
) -> dict:
    """
    Returns:
    {
        advice: str,
        topic: str,    # 'nutrition' | 'workout' | 'supplement' | 'general_fitness'
    }
    """
    guidelines = _load_guidelines()

    # Build context about this specific member if available
    member_note = ""
    if member_context:
        goal = member_context.get("fitness_goal") or "general fitness"
        plan = member_context.get("service_plan") or ""
        diet_pref = member_context.get("diet_preference") or ""
        time_pref = member_context.get("preferred_workout_time") or ""
        parts = []
        if goal: parts.append(f"Goal: {goal}")
        if plan: parts.append(f"Plan: {plan}")
        if diet_pref: parts.append(f"Diet preference: {diet_pref}")
        if time_pref: parts.append(f"Workout time: {time_pref}")
        if parts:
            member_note = "\n\nMember context: " + " · ".join(parts)

    system_prompt = BASE_SYSTEM + guidelines + member_note

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": query},
            ],
            max_tokens=350,
            temperature=0.7,
        )
        advice = response.choices[0].message.content.strip()

        # Simple topic detection
        q_lower = query.lower()
        if any(w in q_lower for w in ["eat", "food", "meal", "protein", "diet", "nutrition", "carb"]):
            topic = "nutrition"
        elif any(w in q_lower for w in ["supplement", "creatine", "whey", "bcaa"]):
            topic = "supplement"
        elif any(w in q_lower for w in ["exercise", "workout", "train", "muscle", "weight", "fat"]):
            topic = "workout"
        else:
            topic = "general_fitness"

        return {"advice": advice, "topic": topic}

    except Exception as e:
        logger.error(f"Diet agent failed: {e}")
        return {
            "advice": "I'm having trouble fetching fitness advice right now. Please try again in a moment.",
            "topic": "general_fitness",
        }