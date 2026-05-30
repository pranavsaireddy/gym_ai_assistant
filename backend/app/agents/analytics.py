# backend/app/agents/analytics.py
"""
Analytics Agent — Owner / Staff Only
======================================
Computes gym-wide stats on every call (no caching — data must be live),
then calls Groq to reason about the data in context of the owner's question.
"""
import asyncio
import logging
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)


def _call_groq(system: str, user: str, max_tokens: int, temperature: float) -> str:
    resp = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


async def run_analytics(db: AsyncSession, user_query: str = "") -> dict:
    """
    Returns:
    {
        analysis: str,               # LLM-generated insight for the owner's question
        total_members, active_members, inactive_members,
        irregular_members, not_seen_14_days, not_seen_30_days,
        expiring_7_days, expiring_30_days,
        todays_checkins, revenue_this_month, revenue_last_month,
        top_payment_mode, as_of,
        at_risk_members: [{name, dropout_score, days_absent, expiry}, ...]
    }
    """
    today = date.today()
    first_of_month = today.replace(day=1)

    try:
        # ── Member counts ─────────────────────────────────────────────
        counts = await db.execute(text("""
            SELECT
                COUNT(*)                                          AS total,
                COUNT(*) FILTER (WHERE status = 'Active')        AS active,
                COUNT(*) FILTER (WHERE status = 'Inactive')      AS inactive,
                COUNT(*) FILTER (WHERE is_irregular = true)      AS irregular
            FROM members
        """))
        c = counts.fetchone()

        # ── Inactivity ────────────────────────────────────────────────
        not_seen_14 = await db.execute(text("""
            SELECT COUNT(*) FROM members
            WHERE status = 'Active'
              AND last_checkin < :cutoff
        """), {"cutoff": today - timedelta(days=14)})
        not_seen_14_val = not_seen_14.scalar() or 0

        not_seen_30 = await db.execute(text("""
            SELECT COUNT(*) FROM members
            WHERE status = 'Active'
              AND last_checkin < :cutoff
        """), {"cutoff": today - timedelta(days=30)})
        not_seen_30_val = not_seen_30.scalar() or 0

        # ── Expiry alerts ──────────────────────────────────────────────
        exp_7 = await db.execute(text("""
            SELECT COUNT(*) FROM members
            WHERE membership_expiry BETWEEN :today AND :plus7
        """), {"today": today, "plus7": today + timedelta(days=7)})
        exp_7_val = exp_7.scalar() or 0

        exp_30 = await db.execute(text("""
            SELECT COUNT(*) FROM members
            WHERE membership_expiry BETWEEN :today AND :plus30
        """), {"today": today, "plus30": today + timedelta(days=30)})
        exp_30_val = exp_30.scalar() or 0

        # ── Today's check-ins ──────────────────────────────────────────
        todays = await db.execute(text("""
            SELECT COUNT(*) FROM attendance_logs
            WHERE checkin_date = :today
        """), {"today": today})
        todays_val = todays.scalar() or 0

        # ── Revenue ───────────────────────────────────────────────────
        rev_month = await db.execute(text("""
            SELECT COALESCE(SUM(amount_paid), 0) FROM billing_records
            WHERE paid_date >= :first
        """), {"first": first_of_month})
        rev_month_val = float(rev_month.scalar() or 0)

        last_month_start = (first_of_month - timedelta(days=1)).replace(day=1)
        rev_last = await db.execute(text("""
            SELECT COALESCE(SUM(amount_paid), 0) FROM billing_records
            WHERE paid_date >= :start AND paid_date < :end
        """), {"start": last_month_start, "end": first_of_month})
        rev_last_val = float(rev_last.scalar() or 0)

        # ── Top payment mode ──────────────────────────────────────────
        pay_mode = await db.execute(text("""
            SELECT pay_mode, COUNT(*) as cnt FROM billing_records
            WHERE paid_date >= :first
            GROUP BY pay_mode ORDER BY cnt DESC LIMIT 1
        """), {"first": first_of_month})
        pm_row = pay_mode.fetchone()
        top_mode = pm_row.pay_mode if pm_row else "unknown"

        # ── Top 10 at-risk members ────────────────────────────────────
        at_risk = await db.execute(text("""
            SELECT name, phone, dropout_score, last_checkin, membership_expiry
            FROM members
            WHERE status = 'Active' AND dropout_score >= 0.5
            ORDER BY dropout_score DESC
            LIMIT 10
        """))
        at_risk_rows = at_risk.fetchall()
        at_risk_list = []
        for r in at_risk_rows:
            days_absent = (today - r.last_checkin).days if r.last_checkin else None
            at_risk_list.append({
                "name":          r.name,
                "dropout_score": round(float(r.dropout_score or 0), 2),
                "days_absent":   days_absent,
                "expiry":        str(r.membership_expiry) if r.membership_expiry else None,
            })

        # ── LLM reasoning — answers the owner's actual question ────────
        at_risk_summary = "\n".join(
            f"  {r['name']}: dropout score {r['dropout_score']}, "
            f"{r['days_absent']} days absent, expires {r['expiry']}"
            for r in at_risk_list
        ) or "  None"
        data_block = (
            f"Date: {today}\n"
            f"Total members: {int(c.total or 0)} "
            f"(Active: {int(c.active or 0)}, Inactive: {int(c.inactive or 0)}, "
            f"Irregular: {int(c.irregular or 0)})\n"
            f"Active members not seen in 14 days: {int(not_seen_14_val)}\n"
            f"Active members not seen in 30 days: {int(not_seen_30_val)}\n"
            f"Memberships expiring in 7 days: {int(exp_7_val)}\n"
            f"Memberships expiring in 30 days: {int(exp_30_val)}\n"
            f"Today's check-ins: {int(todays_val)}\n"
            f"Revenue this month: ₹{rev_month_val:,.0f}\n"
            f"Revenue last month: ₹{rev_last_val:,.0f}\n"
            f"Top payment mode this month: {top_mode}\n"
            f"Top at-risk members (by dropout score):\n{at_risk_summary}"
        )
        system_prompt = (
            "You are a gym business analyst for Muscletech Fitness, Hyderabad, India. "
            "You receive gym-wide membership and revenue stats and the owner's question. "
            "Answer in 3-4 sentences. "
            "If asked who to call first, name specific members sorted by dropout score and days absent. "
            "If asked about revenue, compare this month vs last month directly. "
            "If asked about retention, assess the active vs inactive ratio and at-risk count. "
            "Be analytical and actionable — give the owner concrete next steps."
        )
        user_content = (
            f"Owner question: {user_query or 'Give me a summary of how the gym is doing'}\n\n"
            f"Data:\n{data_block}"
        )
        try:
            analysis = await asyncio.to_thread(
                _call_groq, system_prompt, user_content, 300, 0.3
            )
        except Exception as exc:
            logger.warning(f"Analytics LLM call failed: {exc}")
            analysis = (
                f"{int(c.active or 0)} active members, ₹{rev_month_val:,.0f} revenue this month, "
                f"{int(exp_7_val)} memberships expiring in 7 days."
            )

        return {
            "analysis":           analysis,
            "total_members":      int(c.total or 0),
            "active_members":     int(c.active or 0),
            "inactive_members":   int(c.inactive or 0),
            "irregular_members":  int(c.irregular or 0),
            "not_seen_14_days":   int(not_seen_14_val),
            "not_seen_30_days":   int(not_seen_30_val),
            "expiring_7_days":    int(exp_7_val),
            "expiring_30_days":   int(exp_30_val),
            "todays_checkins":    int(todays_val),
            "revenue_this_month": rev_month_val,
            "revenue_last_month": rev_last_val,
            "top_payment_mode":   top_mode,
            "at_risk_members":    at_risk_list,
            "as_of":              str(today),
        }

    except Exception as e:
        logger.error(f"Analytics agent failed: {e}")
        return {"analysis": "Analytics unavailable.", "error": str(e), "as_of": str(today)}