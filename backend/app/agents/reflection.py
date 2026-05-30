# backend/app/agents/reflection.py
"""
Reflection Agent
================
Runs AFTER the reply is delivered, when the member's NEXT message arrives.
Reads the previous turn's data and classifies the outcome.
Updates episodic memory outcome + semantic user model.

This is the learning loop — what makes the system improve over time.
"""
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from .memory import episodic_update_outcome, semantic_update

logger = logging.getLogger(__name__)

# Signals that indicate a POSITIVE response
_POSITIVE_SIGNALS = {
    "thanks", "thank you", "thx", "great", "awesome", "perfect", "nice",
    "good", "yes", "yeah", "yep", "exactly", "that helps", "helpful",
    "got it", "understood", "makes sense", "will do", "i will", "ok cool",
    "sounds good", "appreciate", "love it", "😊", "👍", "🙏", "💪",
}

# Signals that indicate NEGATIVITY or frustration
_NEGATIVE_SIGNALS = {
    "no", "nope", "wrong", "bad", "useless", "terrible", "hate", "stupid",
    "not helpful", "doesn't help", "stop", "quit", "leave me alone",
    "don't want", "not interested", "irrelevant",
}


async def run_reflection(
    db:                  AsyncSession,
    member_id:           str,
    previous_user_msg:   str,
    previous_reply:      str,
    new_user_message:    str,
    previous_agents:     list[str],
    previous_mood:       str = "unknown",
) -> dict:
    """
    Called at the START of every turn (before the planner runs).
    Looks at the member's new message to classify how the previous reply landed.

    Args:
        previous_user_msg:  What the member said last turn
        previous_reply:     What the assistant replied last turn
        new_user_message:   What the member just said (this is the signal)
        previous_agents:    Which agents ran last turn

    Returns:
        {
            outcome: str,          # what happened
            user_model_updates: {} # what to write to semantic memory
        }
    """
    outcome = _classify_outcome(new_user_message, previous_reply)
    user_model_updates = _derive_user_model_updates(
        outcome, new_user_message, previous_agents, previous_mood
    )

    # Update episodic memory outcome on the previous turn's row
    await episodic_update_outcome(db, member_id, outcome)

    # Update semantic user model with any learned facts
    if user_model_updates:
        await semantic_update(db, member_id, user_model_updates)
        logger.info(f"Reflection: updated user model for {member_id}: {user_model_updates}")

    logger.info(f"Reflection for {member_id}: outcome={outcome}")
    return {
        "outcome":            outcome,
        "user_model_updates": user_model_updates,
    }


def _classify_outcome(new_message: str, previous_reply: str) -> str:
    """
    Classify what happened after the previous reply.
    Simple signal-based classification — no LLM needed here.
    """
    msg = new_message.lower().strip()
    words = set(msg.split())

    # Follow-up question (member engaged and asked more)
    question_words = {"what", "how", "why", "when", "where", "which", "can", "could", "should", "is", "are", "do", "does"}
    if msg.endswith("?") or (words & question_words and len(msg.split()) <= 12):
        return "follow_up_asked"

    # Positive response
    if words & _POSITIVE_SIGNALS or any(s in msg for s in _POSITIVE_SIGNALS):
        return "positive_response"

    # Negative response
    if words & _NEGATIVE_SIGNALS or any(s in msg for s in _NEGATIVE_SIGNALS):
        return "negative_response"

    # Very short reply — probably disengaged or just continuing
    if len(msg) <= 4:
        return "ignored"

    # Default — they continued the conversation, that's positive
    return "positive_response"


def _derive_user_model_updates(
    outcome:         str,
    new_message:     str,
    previous_agents: list[str],
    previous_mood:   str,
) -> dict:
    """
    Derive what we learned about this member from the interaction.
    Returns updates to write to the members user-model columns.
    """
    updates = {}
    msg = new_message.lower()

    # ── Detect mood from new message ──────────────────────────────────
    if any(w in msg for w in ["tired", "exhausted", "busy", "hectic", "stressed", "can't make it"]):
        updates["last_mood"] = "disengaged"
    elif any(w in msg for w in ["great", "amazing", "love", "awesome", "good", "happy", "excited"]):
        updates["last_mood"] = "positive"
    elif any(w in msg for w in ["frustrated", "useless", "not working", "annoyed", "hate"]):
        updates["last_mood"] = "frustrated"
    elif outcome == "follow_up_asked":
        updates["last_mood"] = "positive"   # engaged = positive signal
    elif outcome == "ignored":
        updates["last_mood"] = "disengaged"

    # ── Detect workout time preference ───────────────────────────────
    if any(w in msg for w in ["morning", "6am", "7am", "8am", "early morning"]):
        updates["preferred_workout_time"] = "morning"
    elif any(w in msg for w in ["evening", "6pm", "7pm", "8pm", "after work", "after office"]):
        updates["preferred_workout_time"] = "evening"
    elif any(w in msg for w in ["afternoon", "lunch", "midday", "2pm", "3pm"]):
        updates["preferred_workout_time"] = "afternoon"

    # ── Detect diet preference ────────────────────────────────────────
    if any(w in msg for w in ["vegetarian", "veg", "no meat", "no chicken"]):
        updates["diet_preference"] = "vegetarian"
    elif any(w in msg for w in ["vegan", "no dairy", "plant based"]):
        updates["diet_preference"] = "vegan"
    elif any(w in msg for w in ["non veg", "non-veg", "chicken", "eggs", "meat", "fish"]):
        updates["diet_preference"] = "non-vegetarian"

    # ── Detect fitness goal ───────────────────────────────────────────
    if any(w in msg for w in ["lose weight", "fat loss", "cut", "slim", "lose fat"]):
        updates["fitness_goal"] = "fat loss"
    elif any(w in msg for w in ["build muscle", "bulk", "gain", "strength", "mass"]):
        updates["fitness_goal"] = "muscle gain"
    elif any(w in msg for w in ["cardio", "stamina", "endurance", "run", "fitness"]):
        updates["fitness_goal"] = "cardio and fitness"

    # ── Detect response style preference ─────────────────────────────
    # If they give very short replies consistently, they prefer terse
    if len(new_message.strip()) <= 15 and outcome != "follow_up_asked":
        updates["response_style"] = "terse"
    # If they engage with long replies and ask follow-ups, they like detail
    elif len(new_message.strip()) >= 80 or outcome == "follow_up_asked":
        updates["response_style"] = "detailed"

    return updates