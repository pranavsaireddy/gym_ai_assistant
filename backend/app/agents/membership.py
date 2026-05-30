# backend/app/agents/membership.py
"""
Membership Agent
================
Fetches plan, expiry, and billing data, then calls Groq to reason about it
in context of the member's actual question. Returns analysis + raw urgency
signals for the planner's proactive triggers.
"""
import asyncio
import logging
from datetime import date
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


async def run_membership(
    member_id: str,
    db: AsyncSession,
    user_query: str = "",
    member_context: dict | None = None,
) -> dict:
    """
    Returns:
    {
        analysis: str,               # LLM-generated insight (falls back to urgency_message)
        status: str,
        service_plan: str,
        membership_expiry: str,
        days_to_expiry: int | None,  # planner reads this for proactive signals
        urgency_level: str,          # 'expired' | 'critical' | 'warning' | 'ok'
        urgency_message: str,        # kept as fallback
        total_bills: int,
        last_invoiced: str | None,
        last_payment_amount: float,
        last_payment_date: str,
        last_payment_mode: str,
        amount_pending: float,       # planner reads this for proactive signals
        billing_history: [{date, amount, mode, service}, ...],  # last 5
    }
    """
    today = date.today()

    try:
        # ── Member core ───────────────────────────────────────────────
        mrow = await db.execute(text("""
            SELECT status, service_plan, membership_expiry,
                   total_bills, last_invoiced
            FROM members
            WHERE yoactiv_member_id = :mid
        """), {"mid": member_id})
        m = mrow.fetchone()

        if not m:
            return _empty_membership()

        days_left = None
        if m.membership_expiry:
            days_left = (m.membership_expiry - today).days

        urgency_level, urgency_message = _compute_urgency(m.status, days_left)

        # ── Latest billing records (last 5) ───────────────────────────
        bill_rows = await db.execute(text("""
            SELECT paid_date, amount_paid, amount_pending,
                   pay_mode, service_name
            FROM billing_records
            WHERE yoactiv_member_id = :mid
            ORDER BY paid_date DESC
            LIMIT 5
        """), {"mid": member_id})
        bills = bill_rows.fetchall()

        last_payment_amount = 0.0
        last_payment_date   = "never"
        last_payment_mode   = "unknown"
        amount_pending      = 0.0

        if bills:
            b = bills[0]
            last_payment_amount = float(b.amount_paid or 0)
            last_payment_date   = str(b.paid_date) if b.paid_date else "unknown"
            last_payment_mode   = b.pay_mode or "unknown"
            amount_pending      = float(b.amount_pending or 0)

        billing_history = []
        for b in bills:
            billing_history.append({
                "date":    str(b.paid_date) if b.paid_date else "unknown",
                "amount":  float(b.amount_paid or 0),
                "mode":    b.pay_mode or "unknown",
                "service": b.service_name or "",
            })

        # ── LLM reasoning — answers the member's actual question ───────
        ctx = member_context or {}
        data_block = (
            f"Status: {m.status or 'Unknown'}, Plan: {m.service_plan or 'Not specified'}\n"
            f"Expiry: {m.membership_expiry} ({days_left} days left)\n"
            f"Last payment: ₹{last_payment_amount} on {last_payment_date} via {last_payment_mode}\n"
            f"Pending balance: ₹{amount_pending}\n"
            f"Total bills on record: {int(m.total_bills or 0)}\n"
            f"Recent billing: {billing_history[:3]}\n"
            f"Member fitness goal: {ctx.get('fitness_goal', 'not specified')}"
        )
        system_prompt = (
            "You are a membership advisor for Muscletech Fitness gym in Hyderabad, India. "
            "Given a member's plan, billing data, and their question, answer in 2-3 sentences. "
            "If asked about value or renewal, reason using their plan, payment history, and goals. "
            "Acknowledge expiry naturally if it is close. Do not invent amounts or dates."
        )
        user_content = (
            f"Member question: {user_query or 'Tell me about my membership'}\n\n"
            f"Data:\n{data_block}"
        )
        try:
            analysis = await asyncio.to_thread(
                _call_groq, system_prompt, user_content, 150, 0.4
            )
        except Exception as exc:
            logger.warning(f"Membership LLM call failed for {member_id}: {exc}")
            analysis = urgency_message

        return {
            "analysis":             analysis,
            "status":               m.status or "Unknown",
            "service_plan":         m.service_plan or "Not specified",
            "membership_expiry":    str(m.membership_expiry) if m.membership_expiry else None,
            "days_to_expiry":       days_left,
            "urgency_level":        urgency_level,
            "urgency_message":      urgency_message,
            "total_bills":          int(m.total_bills or 0),
            "last_invoiced":        str(m.last_invoiced) if m.last_invoiced else None,
            "last_payment_amount":  last_payment_amount,
            "last_payment_date":    last_payment_date,
            "last_payment_mode":    last_payment_mode,
            "amount_pending":       amount_pending,
            "billing_history":      billing_history,
        }

    except Exception as e:
        logger.error(f"Membership agent failed for {member_id}: {e}")
        return _empty_membership()


def _compute_urgency(status: str, days_left: int | None) -> tuple[str, str]:
    """Return (urgency_level, urgency_message) for personality layer."""
    if status and status.lower() in ("inactive", "expired"):
        return (
            "expired",
            "Membership has EXPIRED. Mention renewal clearly but without pressure.",
        )
    if days_left is None:
        return ("ok", "Membership data is not available.")
    if days_left < 0:
        return (
            "expired",
            f"Membership expired {abs(days_left)} days ago. Gently but clearly mention renewal.",
        )
    if days_left <= 2:
        return (
            "critical",
            f"URGENT — membership expires in {days_left} day(s). Raise this prominently.",
        )
    if days_left <= 7:
        return (
            "warning",
            f"Membership expires in {days_left} days. Mention renewal once, naturally.",
        )
    return ("ok", f"{days_left} days remaining. No renewal pressure needed.")


def _empty_membership() -> dict:
    return {
        "analysis": "No membership data found.",
        "status": "Unknown", "service_plan": "Unknown",
        "membership_expiry": None, "days_to_expiry": None,
        "urgency_level": "ok", "urgency_message": "No membership data found.",
        "total_bills": 0, "last_invoiced": None,
        "last_payment_amount": 0, "last_payment_date": "never",
        "last_payment_mode": "unknown", "amount_pending": 0,
        "billing_history": [],
    }