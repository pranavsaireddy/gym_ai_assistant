# backend/app/agents/personality.py
"""
Personality Layer
=================
Assembles the system prompt from all agent outputs and member context.
This function is PURE — no LLM call, no DB. Just prompt engineering.
The Groq call happens in chat.py after this returns.

Takes:
  member            — semantic memory dict (from memory.semantic_fetch)
  retrieved_memories — top-k episodic memories
  agent_outputs     — structured data from attendance/membership/diet/analytics
  user_message      — raw member message (for context injection)
  plan_steps        — which agents ran this turn
  is_proactive      — True when the system is initiating (not responding)

Returns:
  str — a complete system prompt ready to pass as {"role":"system",...}
"""
from __future__ import annotations

import json
from typing import Optional


# ══════════════════════════════════════════════════════════════════
# CORE IDENTITY BLOCK — constant across all requests
# ══════════════════════════════════════════════════════════════════

_IDENTITY = """You are the AI coach at Muscletech Fitness, a gym in Bandlaguda Jagir, Hyderabad, India.
You know this member personally and care about their progress.
You are warm, encouraging, and practical — like a knowledgeable friend who happens to work at the gym.

Rules:
- NEVER reveal the member's phone number or any other member's data.
- Keep replies concise (2-4 sentences) unless the member asks for a detailed plan.
- Mix factual data with genuine human warmth.
- Use Indian English naturally (it's fine to say "na", "yaar", "bhai" occasionally, but don't overdo it).
- Respond only in English.
- If you don't know something, say so honestly — never make up membership or billing data.
- Do not use bullet points unless the member explicitly asks for a list."""


# ══════════════════════════════════════════════════════════════════
# TONE MAP — maps mood/response_style to a one-line tone instruction
# ══════════════════════════════════════════════════════════════════

_TONE: dict[str, str] = {
    # response_style
    "terse":        "This member prefers short replies. Keep it to 1-2 sentences max.",
    "detailed":     "This member likes thorough answers. You can be more detailed here.",
    "motivational": "Be warm and energetic. Celebrate their wins.",
    # mood overrides (checked first)
    "frustrated":   "Member seems frustrated or tired. Be extra gentle, validate their feelings before giving advice.",
    "disengaged":   "Member seems disengaged. Be warm but brief — don't overwhelm them.",
    "positive":     "Member is in a positive mood. Match their energy.",
}


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def build_system_prompt(
    member:             dict,
    retrieved_memories: list[dict],
    agent_outputs:      dict,
    user_message:       str,
    plan_steps:         list[str],
    is_proactive:       bool = False,
) -> str:
    """
    Assembles the full system prompt.
    Sections are added only when relevant data exists — keeps prompts tight.
    """
    parts: list[str] = [_IDENTITY]

    # ── Tone ──────────────────────────────────────────────────────
    mood          = member.get("last_mood", "unknown")
    response_style = member.get("response_style", "motivational")
    tone = _TONE.get(mood) or _TONE.get(response_style, "")
    if tone:
        parts.append(f"\nTONE: {tone}")

    # ── Member profile ────────────────────────────────────────────
    parts.append(_build_member_section(member))

    # ── Episodic memories ─────────────────────────────────────────
    memory_block = _build_memory_section(retrieved_memories)
    if memory_block:
        parts.append(memory_block)

    # ── Agent outputs (per agent that ran) ────────────────────────
    for agent_name in plan_steps:
        data = agent_outputs.get(agent_name)
        if not data:
            continue
        block = _build_agent_section(agent_name, data)
        if block:
            parts.append(block)

    # ── Proactive signals (injected urgency flags) ────────────────
    signals = agent_outputs.get("_proactive_signals", [])
    if signals:
        parts.append("\nALERT — mention these naturally in your reply:")
        for s in signals:
            parts.append(f"  • {s}")

    # ── Proactive framing ─────────────────────────────────────────
    if is_proactive:
        parts.append(
            "\nThis message is sent PROACTIVELY by the system (not in response to a user query). "
            "Reach out warmly, as if you noticed something and wanted to check in. "
            "Do not mention 'the system' or 'AI' — just speak naturally."
        )

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════
# SECTION BUILDERS
# ══════════════════════════════════════════════════════════════════

def _build_member_section(m: dict) -> str:
    name    = m.get("name", "the member")
    status  = m.get("status", "Unknown")
    plan    = m.get("service_plan") or "Not specified"
    expiry  = m.get("membership_expiry") or "Unknown"
    days    = m.get("days_to_expiry")
    goal    = m.get("fitness_goal") or "not set"
    diet    = m.get("diet_preference") or "not set"
    workout_time = m.get("preferred_workout_time") or "not set"
    checkins_total = m.get("total_checkins", 0)
    last_seen = m.get("last_checkin", "never")

    days_str = f"{days} days left" if days is not None else "unknown"
    irregular_note = " [Yoactiv flags this member as irregular]" if m.get("is_irregular") else ""

    return f"""
MEMBER PROFILE:
  Name: {name}
  Status: {status}{irregular_note}
  Plan: {plan}
  Expiry: {expiry} ({days_str})
  Total check-ins: {checkins_total}
  Last seen: {last_seen}
  Goal: {goal}
  Diet preference: {diet}
  Preferred workout time: {workout_time}"""


def _build_memory_section(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = ["\nRELEVANT PAST CONVERSATIONS (for context — do not quote directly):"]
    for m in memories[:3]:
        ts  = m.get("timestamp", "")
        usr = (m.get("user_message") or "")[:100]
        ast = (m.get("assistant_reply") or "")[:100]
        outcome = m.get("outcome", "")
        lines.append(f"  [{ts}] Member said: \"{usr}\" → You replied: \"{ast}\" ({outcome})")
    return "\n".join(lines)


def _build_agent_section(name: str, data: dict) -> str:
    if "error" in data:
        return ""

    if name == "attendance":
        return _attendance_block(data)
    if name == "membership":
        return _membership_block(data)
    if name == "diet":
        return _diet_block(data)
    if name == "analytics":
        return _analytics_block(data)
    if name == "occupancy":
        return _occupancy_block(data)
    return ""


def _attendance_block(d: dict) -> str:
    analysis = d.get("analysis") or d.get("pattern_signal", "")
    chart    = d.get("ascii_chart", "")
    visits   = d.get("visits_this_month", 0)
    streak   = d.get("current_streak", 0)
    block = f"\nATTENDANCE ANALYSIS:\n  {analysis}"
    if chart:
        block += f"\n  30-day chart: {chart}"
    block += f"\n  (Raw: {visits} visits this month, {streak}-day current streak)"
    return block


def _membership_block(d: dict) -> str:
    analysis = d.get("analysis") or d.get("urgency_message", "")
    block = f"\nMEMBERSHIP ANALYSIS:\n  {analysis}"
    pending = d.get("amount_pending", 0)
    if pending and float(pending) > 0:
        block += f"\n  (Note: ₹{pending} pending balance)"
    urgency = d.get("urgency_level", "ok")
    if urgency in ("critical", "expired"):
        block += f"\n  (Urgency: {urgency} — {d.get('days_to_expiry', '?')} days to expiry)"
    return block


def _diet_block(d: dict) -> str:
    advice = d.get("advice", "")
    topic  = d.get("topic", "general_fitness")
    if not advice:
        return ""
    return f"""
FITNESS/DIET ADVICE (already researched — weave this into your reply naturally):
  Topic: {topic}
  Advice: {advice}"""


def _analytics_block(d: dict) -> str:
    analysis = d.get("analysis", "")
    block = f"\nANALYTICS ANALYSIS (owner view):\n  {analysis}"
    at_risk = d.get("at_risk_members", [])
    if at_risk:
        names = [r["name"] for r in at_risk[:5]]
        block += f"\n  At-risk members: {', '.join(names)}"
    return block


def _occupancy_block(d: dict) -> str:
    if d.get("source") == "error":
        return ""
    return f"""
GYM OCCUPANCY (live):
  Currently in gym: {d.get('count', 'unknown')} people
  Status: {d.get('peak_signal', 'unknown')}
  Suggestion: {d.get('suggestion', '')}"""
