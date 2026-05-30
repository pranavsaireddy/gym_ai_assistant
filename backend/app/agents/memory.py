# backend/app/agents/memory.py
"""
Memory Layer — FIXED VERSION
Fix 1: CAST(:vec AS vector) instead of :vec::vector
Fix 2: await db.rollback() after any failed query
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading all-MiniLM-L6-v2 embedding model...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _embedder

def embed(text_input: str) -> list[float]:
    model = get_embedder()
    vec = model.encode(text_input, normalize_embeddings=True)
    return vec.tolist()

def _vec_str(vec: list[float]) -> str:
    return "[" + ",".join(str(round(v, 6)) for v in vec) + "]"

# ── WORKING MEMORY ──────────────────────────────────────────────────
_working_store: dict[str, dict] = {}

def working_memory_init(member_id: str) -> dict:
    _working_store[member_id] = {
        "member_id": member_id, "current_plan": [], "agent_outputs": {},
        "detected_intent": None, "detected_mood": "unknown",
        "detected_urgency": "normal", "is_proactive": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    return _working_store[member_id]

def working_memory_get(member_id: str) -> dict:
    return _working_store.get(member_id, {})

def working_memory_set(member_id: str, key: str, value) -> None:
    if member_id not in _working_store:
        working_memory_init(member_id)
    _working_store[member_id][key] = value

def working_memory_clear(member_id: str) -> None:
    _working_store.pop(member_id, None)

# ── EPISODIC MEMORY ─────────────────────────────────────────────────
async def episodic_store(
    db: AsyncSession, member_id: str, user_message: str,
    assistant_reply: str, agents_used: list[str],
    mood: str = "unknown", outcome: str = "unknown",
) -> None:
    try:
        vec = embed(user_message.strip())
        await db.execute(text("""
            INSERT INTO episodic_memory
                (yoactiv_member_id, user_message, assistant_reply,
                 agent_used, mood, outcome, embedding)
            VALUES
                (:mid, :user_msg, :reply, :agents, :mood, :outcome,
                 CAST(:vec AS vector))
        """), {
            "mid": member_id, "user_msg": user_message[:2000],
            "reply": assistant_reply[:2000], "agents": ",".join(agents_used),
            "mood": mood, "outcome": outcome, "vec": _vec_str(vec),
        })
        await db.commit()
        logger.debug(f"Episodic memory saved for {member_id}")
    except Exception as e:
        logger.error(f"episodic_store failed for {member_id}: {e}")
        try:
            await db.rollback()
        except Exception:
            pass

async def episodic_retrieve(
    db: AsyncSession, member_id: str, query: str, top_k: int = 5,
) -> list[dict]:
    try:
        vec = embed(query)
        vs = _vec_str(vec)
        result = await db.execute(text("""
            SELECT
                timestamp, user_message, assistant_reply, mood, outcome,
                1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM episodic_memory
            WHERE yoactiv_member_id = :mid
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
        """), {"mid": member_id, "vec": vs, "k": top_k})
        rows = result.fetchall()
        return [{
            "timestamp":       str(row.timestamp)[:16],
            "user_message":    row.user_message or "",
            "assistant_reply": (row.assistant_reply or "")[:200],
            "mood":            row.mood or "unknown",
            "outcome":         row.outcome or "unknown",
            "similarity":      round(float(row.similarity), 3),
        } for row in rows]
    except Exception as e:
        logger.warning(f"episodic_retrieve failed for {member_id}: {e}")
        try:
            await db.rollback()
        except Exception:
            pass
        return []

async def episodic_update_outcome(
    db: AsyncSession, member_id: str, outcome: str,
) -> None:
    try:
        await db.execute(text("""
            UPDATE episodic_memory SET outcome = :outcome
            WHERE id = (
                SELECT id FROM episodic_memory
                WHERE yoactiv_member_id = :mid
                ORDER BY timestamp DESC LIMIT 1
            )
        """), {"outcome": outcome, "mid": member_id})
        await db.commit()
    except Exception as e:
        logger.warning(f"episodic_update_outcome failed: {e}")
        try:
            await db.rollback()
        except Exception:
            pass

# ── SEMANTIC MEMORY ─────────────────────────────────────────────────
async def semantic_fetch(db: AsyncSession, member_id: str) -> dict:
    from datetime import date as date_type
    result = await db.execute(text("""
        SELECT name, status, service_plan, membership_expiry,
               last_invoiced, total_bills, last_checkin, total_checkins,
               is_irregular, dropout_score,
               fitness_goal, preferred_workout_time, diet_preference,
               response_style, last_mood
        FROM members WHERE yoactiv_member_id = :mid
    """), {"mid": member_id})
    row = result.fetchone()
    if not row:
        return {}
    today = date_type.today()
    days_left = (row.membership_expiry - today).days if row.membership_expiry else None
    return {
        "name": row.name, "status": row.status,
        "service_plan": row.service_plan,
        "membership_expiry": str(row.membership_expiry) if row.membership_expiry else None,
        "days_to_expiry": days_left,
        "total_checkins": row.total_checkins or 0,
        "last_checkin": str(row.last_checkin) if row.last_checkin else "never",
        "is_irregular": row.is_irregular or False,
        "dropout_score": float(row.dropout_score or 0.0),
        "fitness_goal": row.fitness_goal,
        "preferred_workout_time": row.preferred_workout_time,
        "diet_preference": row.diet_preference,
        "response_style": row.response_style or "motivational",
        "last_mood": row.last_mood or "unknown",
    }

async def semantic_update(
    db: AsyncSession, member_id: str, updates: dict,
) -> None:
    allowed = {"fitness_goal","preferred_workout_time","diet_preference","response_style","last_mood"}
    safe = {k: v for k, v in updates.items() if k in allowed}
    if not safe:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in safe)
    safe["mid"] = member_id
    try:
        await db.execute(
            text(f"UPDATE members SET {set_clause} WHERE yoactiv_member_id = :mid"),
            safe,
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"semantic_update failed: {e}")
        try:
            await db.rollback()
        except Exception:
            pass