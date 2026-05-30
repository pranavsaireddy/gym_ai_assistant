# backend/app/routes/chat.py
"""
Chat Route — POST /chat
========================
Full orchestration of the cognitive pipeline per request:

1. JWT validation → get member
2. Reflection (previous turn outcome) 
3. Load all three memory layers
4. Perception (intent + mood)
5. Planner (decide + execute agents)
6. Personality (assemble prompt + Groq call)
7. Save to episodic memory
8. Return reply

One endpoint. All intelligence lives in the agents.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from groq import Groq

from app.database import get_db, ChatMessage
from app.auth.dependencies import get_current_member
from app.config import settings

from app.agents.memory import (
    working_memory_init,
    working_memory_clear,
    episodic_retrieve,
    episodic_store,
    semantic_fetch,
)
from app.agents.perception import run_perception
from app.agents.planner    import run_plan
from app.agents.reflection import run_reflection
from app.agents.personality import build_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
groq_client = Groq(api_key=settings.GROQ_API_KEY)


class ChatRequest(BaseModel):
    message: str


@router.post("")
async def chat(
    body: ChatRequest,
    current_member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Main member chatbot endpoint.
    Full cognitive pipeline on every message.
    """
    user_message = body.message.strip()
    if not user_message:
        return {"reply": "Go ahead — ask me anything!", "agent": "none"}

    member_id = current_member.yoactiv_member_id
    role      = "member"

    try:
        # ── 1. Init working memory ────────────────────────────────────
        wm = working_memory_init(member_id)

        # ── 2. Reflection on previous turn ───────────────────────────
        # Load the last chat exchange from DB to classify how it landed
        prev = await _load_previous_turn(db, member_id)
        if prev:
            await run_reflection(
                db                  = db,
                member_id           = member_id,
                previous_user_msg   = prev["user_msg"],
                previous_reply      = prev["assistant_reply"],
                new_user_message    = user_message,
                previous_agents     = prev["agents"],
                previous_mood       = prev["mood"],
            )

        # ── 3. Load all memory layers ─────────────────────────────────
        member_data = await semantic_fetch(db, member_id)
        if not member_data:
            raise HTTPException(status_code=404, detail="Member not found")

        retrieved_memories = await episodic_retrieve(
            db, member_id, user_message, top_k=5
        )

        # ── 4. Perception ─────────────────────────────────────────────
        perception = run_perception(user_message, role)
        mood       = perception.get("mood", "unknown")
        category   = perception.get("category", "GENERAL")

        logger.info(f"[{member_id}] category={category} mood={mood}")

        # ── 5. Planner: decide + execute agents ───────────────────────
        plan_result = await run_plan(
            member_id    = member_id,
            member_data  = member_data,
            perception   = perception,
            user_message = user_message,
            db           = db,
            role         = role,
        )

        plan_steps        = plan_result["plan_steps"]
        agent_outputs     = plan_result["agent_outputs"]
        proactive_signals = plan_result["proactive_signals"]

        # ── 6. Personality layer: build system prompt + Groq call ─────
        # Merge proactive signals into agent_outputs for the prompt builder
        agent_outputs["_proactive_signals"] = proactive_signals

        system_prompt = build_system_prompt(
            member            = member_data,
            retrieved_memories = retrieved_memories,
            agent_outputs      = agent_outputs,
            user_message       = user_message,
            plan_steps         = plan_steps,
            is_proactive       = False,
        )

        groq_response = groq_client.chat.completions.create(
            model    = settings.GROQ_MODEL,
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            max_tokens  = 250,
            temperature = 0.72,
        )
        reply = groq_response.choices[0].message.content.strip()

        # ── 7. Save to DB + episodic memory ──────────────────────────
        # Save to chat_messages table (existing)
        db.add(ChatMessage(
            yoactiv_member_id = member_id,
            role              = "user",
            content           = user_message,
        ))
        db.add(ChatMessage(
            yoactiv_member_id = member_id,
            role              = "assistant",
            content           = reply,
            agent_used        = ",".join(plan_steps),
        ))
        await db.commit()

        # Save to episodic memory (async, non-blocking mood from perception)
        await episodic_store(
            db             = db,
            member_id      = member_id,
            user_message   = user_message,
            assistant_reply = reply,
            agents_used    = plan_steps,
            mood           = mood,
            outcome        = "unknown",   # reflection will update this next turn
        )

        # ── 8. Clear working memory ───────────────────────────────────
        working_memory_clear(member_id)

        return {
            "reply":       reply,
            "agent":       ",".join(plan_steps),
            "category":    category,
            "mood":        mood,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat pipeline failed for {member_id}: {e}", exc_info=True)
        working_memory_clear(member_id)
        return {
            "reply": "Something went wrong on my end. Try again in a moment!",
            "agent": "error",
        }


async def _load_previous_turn(db: AsyncSession, member_id: str) -> Optional[dict]:
    """
    Load the last user+assistant exchange from chat_messages.
    Used by reflection to classify how the previous reply landed.
    """
    try:
        result = await db.execute(text("""
            SELECT role, content, agent_used
            FROM chat_messages
            WHERE yoactiv_member_id = :mid
            ORDER BY id DESC
            LIMIT 2
        """), {"mid": member_id})
        rows = result.fetchall()

        if len(rows) < 2:
            return None

        # Rows come newest-first: rows[0]=assistant, rows[1]=user
        assistant_row = None
        user_row      = None
        for r in rows:
            if r.role == "assistant" and not assistant_row:
                assistant_row = r
            if r.role == "user" and not user_row:
                user_row = r

        if not assistant_row or not user_row:
            return None

        return {
            "user_msg":        user_row.content,
            "assistant_reply": assistant_row.content,
            "agents":          (assistant_row.agent_used or "").split(","),
            "mood":            "unknown",  # mood was stored in episodic_memory
        }

    except Exception as e:
        logger.warning(f"Could not load previous turn for {member_id}: {e}")
        return None