# backend/app/agents/planner.py
"""
LangGraph Agent Pipeline
========================
StateGraph with fan-out routing:

  START -> router -> [attendance, membership, diet, analytics, occupancy] -> collect -> END

The router decides which agent nodes to activate (in parallel).
Each agent node creates its own DB session — safe for concurrent execution.
State reducers merge outputs from parallel branches automatically.

Public API: run_plan() — same signature/return shape as before.
"""
from __future__ import annotations

import asyncio
import logging
import operator
from typing import TypedDict, Annotated, Any

from langgraph.graph import StateGraph, START, END
from sqlalchemy.ext.asyncio import AsyncSession

from .attendance import run_attendance
from .membership import run_membership
from .diet      import run_diet
from .analytics import run_analytics
from .occupancy import run_occupancy
from .memory    import working_memory_set

logger = logging.getLogger(__name__)


# ── Routing tables (unchanged from before) ────────────────────────────────────

CATEGORY_PLAN: dict[str, list[str]] = {
    "ATTENDANCE": ["attendance", "membership"],
    "MEMBERSHIP": ["membership", "attendance"],
    "DIET":       ["diet", "attendance"],
    "FITNESS":    ["diet", "attendance"],
    "OCCUPANCY":  ["occupancy"],
    "ANALYTICS":  ["analytics"],
    "GENERAL":    ["attendance", "membership"],
}

ALWAYS_CHECK_EXPIRY_FOR = {"ATTENDANCE", "DIET", "FITNESS", "OCCUPANCY", "GENERAL"}


# ── State ─────────────────────────────────────────────────────────────────────

def _merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}

class GymState(TypedDict):
    member_id:        str
    member_data:      dict
    user_message:     str
    perception:       dict
    role:             str
    agents_to_run:    list[str]
    plan_steps:       list[str]           # set once by router; NOT a reducer — order is deterministic
    # Reducers merge outputs from parallel branches
    agent_outputs:    Annotated[dict, _merge_dicts]
    proactive_signals: Annotated[list, operator.add]


# ── Proactive signal extractor (same logic as before) ─────────────────────────

def _extract_proactive_signals(agent_name: str, output: dict, member_data: dict) -> list[str]:
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
        days    = output.get("days_to_expiry")
        if urgency == "critical":
            signals.append(f"MEMBERSHIP EXPIRES IN {days} DAYS — raise this clearly.")
        elif urgency == "expired":
            signals.append("MEMBERSHIP EXPIRED — mention renewal, but gently.")
        pending = output.get("amount_pending", 0)
        if pending and float(pending) > 0:
            signals.append(f"Has ₹{pending} pending balance — mention once, softly.")

    if agent_name == "occupancy":
        if output.get("peak_signal") == "quiet":
            signals.append("Gym is quiet right now — good moment to invite them in.")

    return signals


# ── Graph nodes ───────────────────────────────────────────────────────────────

def router_node(state: GymState) -> dict:
    """Decide which agents to run and write the plan into state."""
    category      = state["perception"].get("category", "GENERAL")
    days_to_expiry = state["member_data"].get("days_to_expiry")

    plan = list(CATEGORY_PLAN.get(category, ["attendance", "membership"]))

    # Always append membership check if expiry is close and not already in plan
    if (
        category in ALWAYS_CHECK_EXPIRY_FOR
        and days_to_expiry is not None
        and days_to_expiry <= 7
        and "membership" not in plan
    ):
        plan.append("membership")

    # Block ANALYTICS for non-staff
    if category == "ANALYTICS" and state["role"] not in ("owner", "staff"):
        logger.warning(f"Member {state['member_id']} tried ANALYTICS — blocked")
        plan = ["attendance", "membership"]

    logger.info(f"LangGraph plan [{state['member_id']}] category={category}: {plan}")
    working_memory_set(state["member_id"], "current_plan", plan)
    # plan_steps is set HERE, once, in the correct order.
    # Agent nodes do NOT write to plan_steps — avoids non-deterministic ordering
    # from parallel completion.
    return {"agents_to_run": plan, "plan_steps": plan}


def route_to_agents(state: GymState) -> list[str]:
    """Conditional edge: fan out to all selected agent nodes in parallel."""
    agents = state.get("agents_to_run", [])
    return agents if agents else ["collect"]


async def attendance_node(state: GymState, config: dict) -> dict:
    try:
        session_factory = config["configurable"]["session_factory"]
        async with session_factory() as db:
            output = await run_attendance(
                state["member_id"], db, user_query=state["user_message"]
            )
    except Exception as e:
        logger.error(f"attendance_node failed: {e}")
        output = {
            "analysis": "Attendance data unavailable.",
            "visits_this_month": 0, "days_missed_this_month": 0,
            "current_streak": 0, "longest_streak_30d": 0,
            "last_checkin": None, "total_checkins": 0,
            "checkins_last_30": [], "recent_logs": [],
            "pattern_signal": "Unable to load.", "ascii_chart": "",
        }
    signals = _extract_proactive_signals("attendance", output, state["member_data"])
    working_memory_set(state["member_id"], "output_attendance", output)
    return {
        "agent_outputs":    {"attendance": output},
        "proactive_signals": signals,
    }


async def membership_node(state: GymState, config: dict) -> dict:
    try:
        session_factory = config["configurable"]["session_factory"]
        async with session_factory() as db:
            output = await run_membership(
                state["member_id"], db,
                user_query=state["user_message"],
                member_context=state["member_data"],
            )
    except Exception as e:
        logger.error(f"membership_node failed: {e}")
        output = {
            "analysis": "Membership data unavailable.",
            "status": "Unknown", "service_plan": "Unknown",
            "membership_expiry": None, "days_to_expiry": None,
            "urgency_level": "ok", "urgency_message": "No data.",
            "total_bills": 0, "last_invoiced": None,
            "last_payment_amount": 0, "last_payment_date": "never",
            "last_payment_mode": "unknown", "amount_pending": 0,
            "billing_history": [],
        }
    signals = _extract_proactive_signals("membership", output, state["member_data"])
    working_memory_set(state["member_id"], "output_membership", output)
    return {
        "agent_outputs":    {"membership": output},
        "proactive_signals": signals,
    }


async def diet_node(state: GymState, config: dict) -> dict:
    try:
        # run_diet is synchronous (Groq call) — run in thread pool
        output = await asyncio.to_thread(
            run_diet, state["user_message"], state["member_data"]
        )
    except Exception as e:
        logger.error(f"diet_node failed: {e}")
        output = {"advice": "Advice unavailable right now.", "topic": "general_fitness"}
    working_memory_set(state["member_id"], "output_diet", output)
    return {
        "agent_outputs":    {"diet": output},
        "proactive_signals": [],
    }


async def analytics_node(state: GymState, config: dict) -> dict:
    try:
        session_factory = config["configurable"]["session_factory"]
        async with session_factory() as db:
            output = await run_analytics(db, user_query=state["user_message"])
    except Exception as e:
        logger.error(f"analytics_node failed: {e}")
        output = {"analysis": "Analytics unavailable.", "error": str(e), "as_of": ""}
    working_memory_set(state["member_id"], "output_analytics", output)
    return {
        "agent_outputs":    {"analytics": output},
        "proactive_signals": [],
    }


async def occupancy_node(state: GymState, config: dict) -> dict:
    try:
        output = await run_occupancy()
    except Exception as e:
        logger.error(f"occupancy_node failed: {e}")
        output = {"count": None, "source": "error", "peak_signal": "unknown", "suggestion": ""}
    signals = _extract_proactive_signals("occupancy", output, state["member_data"])
    working_memory_set(state["member_id"], "output_occupancy", output)
    return {
        "agent_outputs":    {"occupancy": output},
        "proactive_signals": signals,
    }


def collect_node(state: GymState) -> dict:
    """
    Convergence point — LangGraph waits for ALL active parallel branches
    before executing this node. The log below confirms both agents finished.
    """
    completed = list(state.get("agent_outputs", {}).keys())
    logger.info(f"collect_node reached — agents completed: {completed} (planned: {state.get('plan_steps')})")
    return {}


# ── Build and compile graph (once at import time) ─────────────────────────────

def _build_graph():
    builder = StateGraph(GymState)

    builder.add_node("router",     router_node)
    builder.add_node("attendance", attendance_node)
    builder.add_node("membership", membership_node)
    builder.add_node("diet",       diet_node)
    builder.add_node("analytics",  analytics_node)
    builder.add_node("occupancy",  occupancy_node)
    builder.add_node("collect",    collect_node)

    builder.add_edge(START, "router")

    # Fan-out: router → selected agent nodes in parallel
    builder.add_conditional_edges(
        "router",
        route_to_agents,
        ["attendance", "membership", "diet", "analytics", "occupancy", "collect"],
    )

    # All agents converge at collect
    for agent in ["attendance", "membership", "diet", "analytics", "occupancy"]:
        builder.add_edge(agent, "collect")

    builder.add_edge("collect", END)

    return builder.compile()


gym_graph = _build_graph()
logger.info("LangGraph gym_graph compiled successfully")


# ── Public API ────────────────────────────────────────────────────────────────

async def run_plan(
    member_id:       str,
    member_data:     dict,
    perception:      dict,
    user_message:    str | None,
    session_factory: Any,          # AsyncSessionLocal factory, not a session
    role:            str = "member",
) -> dict:
    """
    Invoke the LangGraph pipeline.
    Returns: {plan_steps: [str], agent_outputs: {agent: dict}, proactive_signals: [str]}
    """
    initial_state: GymState = {
        "member_id":        member_id,
        "member_data":      member_data,
        "user_message":     user_message or "",
        "perception":       perception,
        "role":             role,
        "agents_to_run":    [],
        "agent_outputs":    {},
        "proactive_signals": [],
        "plan_steps":       [],
    }

    result = await gym_graph.ainvoke(
        initial_state,
        config={"configurable": {"session_factory": session_factory}},
    )

    return {
        "plan_steps":        result["plan_steps"],
        "agent_outputs":     result["agent_outputs"],
        "proactive_signals": result["proactive_signals"],
    }
