# backend/app/agents/planner.py
"""
Planner / Orchestrator
======================
The brain. Receives perception output + member profile,
decides which agents to run and in what order,
executes them, and collects all structured outputs.

No LangGraph — clean custom async orchestrator.
Transparent, debuggable, no framework magic.
"""
from __future__ import annotations

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .memory import working_memory_get, working_memory_set
from .attendance  import run_attendance
from .membership  import run_membership
from .diet        import run_diet
from .analytics   import run_analytics
from .occupancy   import run_occupancy

logger = logging.getLogger(__name__)


# ── Plan decision table ───────────────────────────────────────────────────────
# Maps perception category to list of agents to run.
# Agents run in the order listed.
# Planner always also checks membership if expiry is within 7 days (injected below).

CATEGORY_PLAN: dict[str, list[str]] = {
    "ATTENDANCE":  ["attendance", "membership"],     # show attendance + flag expiry if close
    "MEMBERSHIP":  ["membership", "attendance"],     # show membership + attendance context
    "DIET":        ["diet", "attendance"],            # diet advice + acknowledge their activity
    "FITNESS":     ["diet", "attendance"],            # fitness = diet agent handles both
    "OCCUPANCY":   ["occupancy"],                     # live headcount only
    "ANALYTICS":   ["analytics"],                     # owner only — enforced in chat route
    "GENERAL":     ["attendance", "membership"],     # default: give them something useful
}

# Categories that always get a membership check appended if expiry ≤ 7 days
ALWAYS_CHECK_EXPIRY_FOR = {"ATTENDANCE", "DIET", "FITNESS", "OCCUPANCY", "GENERAL"}


async def run_plan(
    member_id:    str,
    member_data:  dict,
    perception:   dict,
    user_message: Optional[str],
    db:           AsyncSession,
    role:         str = "member",
) -> dict:
    """
    Execute the full agent plan for this turn.

    Args:
        member_id:    Yoactiv member ID
        member_data:  Semantic memory dict (from memory.semantic_fetch)
        perception:   Output of perception agent
        user_message: Raw member message (None if proactive)
        db:           Async DB session
        role:         'member' | 'owner' | 'staff'

    Returns:
        {
            plan_steps: [str, ...],    # agents that ran
            agent_outputs: {agent: output_dict},
            proactive_signals: [str],  # extra things to mention
        }
    """
    category = perception.get("category", "GENERAL")
    days_to_expiry = member_data.get("days_to_expiry")

    # ── Build agent list ───────────────────────────────────────────────────
    plan: list[str] = list(CATEGORY_PLAN.get(category, ["attendance", "membership"]))

    # Always add membership if expiry is critical and not already in plan
    if (
        category in ALWAYS_CHECK_EXPIRY_FOR
        and days_to_expiry is not None
        and days_to_expiry <= 7
        and "membership" not in plan
    ):
        plan.append("membership")

    # Owner/staff: analytics is allowed
    if category == "ANALYTICS" and role not in ("owner", "staff"):
        logger.warning(f"Member {member_id} tried to access ANALYTICS — blocked")
        plan = ["attendance", "membership"]

    # Store plan in working memory
    working_memory_set(member_id, "current_plan", plan)
    logger.info(f"Plan for {member_id} [{category}]: {plan}")

    # ── Execute agents ─────────────────────────────────────────────────────
    agent_outputs: dict = {}
    proactive_signals: list[str] = []

    for agent_name in plan:
        try:
            output = await _execute_agent(
                agent_name, member_id, member_data, user_message, db
            )
            agent_outputs[agent_name] = output
            working_memory_set(member_id, f"output_{agent_name}", output)

            # Collect proactive signals from agent outputs
            signals = _extract_proactive_signals(agent_name, output, member_data)
            proactive_signals.extend(signals)

        except Exception as e:
            logger.error(f"Agent '{agent_name}' failed for {member_id}: {e}")
            agent_outputs[agent_name] = {"error": str(e)}

    return {
        "plan_steps":        plan,
        "agent_outputs":     agent_outputs,
        "proactive_signals": proactive_signals,
    }


async def _execute_agent(
    name:         str,
    member_id:    str,
    member_data:  dict,
    user_message: Optional[str],
    db:           AsyncSession,
) -> dict:
    """Dispatch to the correct agent function."""
    if name == "attendance":
        return await run_attendance(member_id, db, user_query=user_message or "")

    if name == "membership":
        return await run_membership(member_id, db, user_query=user_message or "", member_context=member_data)

    if name == "diet":
        return run_diet(user_message or "general fitness advice", member_data)

    if name == "analytics":
        return await run_analytics(db, user_query=user_message or "")

    if name == "occupancy":
        return await run_occupancy()

    logger.warning(f"Unknown agent name: {name}")
    return {}


def _extract_proactive_signals(
    agent_name: str,
    output:     dict,
    member_data: dict,
) -> list[str]:
    """
    Look at agent output and generate extra things the personality
    layer should surface even if the member didn't ask.
    These become part of the proactive_signals list in context.
    """
    signals = []

    if agent_name == "attendance":
        streak = output.get("current_streak", 0)
        visits = output.get("visits_this_month", 0)
        if streak >= 5:
            signals.append(f"Member is on a {streak}-day streak — worth celebrating explicitly.")
        if visits == 0:
            signals.append("Member has zero visits this month — be warm and ask what's happening.")

    if agent_name == "membership":
        urgency = output.get("urgency_level", "ok")
        days = output.get("days_to_expiry")
        if urgency == "critical":
            signals.append(f"MEMBERSHIP EXPIRES IN {days} DAYS — raise this clearly.")
        elif urgency == "expired":
            signals.append("MEMBERSHIP EXPIRED — mention renewal, but gently.")
        pending = output.get("amount_pending", 0)
        if pending and float(pending) > 0:
            signals.append(f"Has ₹{pending} pending balance — mention once, softly.")

    if agent_name == "occupancy":
        peak = output.get("peak_signal")
        if peak == "quiet":
            signals.append("Gym is quiet right now — good moment to invite them in.")

    return signals