# backend/app/agents/attendance.py
"""
Attendance Agent
================
Fetches attendance data from DB, then calls Groq to reason about it
in the context of the member's actual question. Returns both the
LLM analysis and raw signals (for planner's proactive triggers).
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


async def run_attendance(member_id: str, db: AsyncSession, user_query: str = "") -> dict:
    """
    Pull attendance data for this member, then call Groq to reason about it
    in context of the member's actual question.

    Returns:
    {
        analysis: str,                  # LLM-generated insight (falls back to pattern_signal)
        visits_this_month: int,
        days_missed_this_month: int,
        current_streak: int,            # planner reads this for proactive signals
        longest_streak_30d: int,
        last_checkin: str | None,
        total_checkins: int,
        checkins_last_30: [str, ...],
        recent_logs: [{date, clock_in, clock_out, location}, ...],
        pattern_signal: str,            # kept as fallback
        ascii_chart: str,
    }
    """
    today = date.today()
    first_of_month = today.replace(day=1)
    thirty_ago = today - timedelta(days=30)

    try:
        # ── Core member stats ──────────────────────────────────────────
        member_row = await db.execute(text("""
            SELECT total_checkins, last_checkin
            FROM members
            WHERE yoactiv_member_id = :mid
        """), {"mid": member_id})
        mrow = member_row.fetchone()
        total_checkins = int(mrow.total_checkins or 0) if mrow else 0
        last_checkin_raw = mrow.last_checkin if mrow else None

        # ── Last 30 days attendance logs ───────────────────────────────
        logs_result = await db.execute(text("""
            SELECT checkin_date, clock_in_time, clock_out_time, location
            FROM attendance_logs
            WHERE yoactiv_member_id = :mid
              AND checkin_date >= :from_date
            ORDER BY checkin_date DESC
        """), {"mid": member_id, "from_date": thirty_ago})
        logs = logs_result.fetchall()

        # Unique dates present in last 30 days
        dates_present_set = sorted(
            {row.checkin_date for row in logs}, reverse=True
        )
        checkins_last_30 = [str(d) for d in dates_present_set]

        # ── This month visits ──────────────────────────────────────────
        days_in_month = (today - first_of_month).days + 1
        visits_this_month = sum(
            1 for d in dates_present_set if d >= first_of_month
        )
        days_missed_this_month = days_in_month - visits_this_month

        # ── Current consecutive streak ─────────────────────────────────
        streak = 0
        check_date = today
        for i in range(60):
            if check_date in dates_present_set or (i == 0 and check_date - timedelta(days=1) in dates_present_set):
                pass
            d_set = set(dates_present_set)
            if check_date in d_set:
                streak += 1
                check_date -= timedelta(days=1)
            elif i == 0:
                # didn't come today — check if yesterday starts a streak
                check_date = today - timedelta(days=1)
                if check_date in d_set:
                    streak += 1
                    check_date -= timedelta(days=1)
                else:
                    break
            else:
                break

        # ── Longest streak in last 30 days ─────────────────────────────
        all_30 = sorted(dates_present_set)
        longest = 0
        cur = 0
        prev = None
        for d in all_30:
            if prev and (d - prev).days == 1:
                cur += 1
            else:
                cur = 1
            longest = max(longest, cur)
            prev = d

        # ── Recent logs (last 10) for display ─────────────────────────
        recent_logs = []
        for row in logs[:10]:
            recent_logs.append({
                "date":      str(row.checkin_date),
                "clock_in":  str(row.clock_in_time) if row.clock_in_time else None,
                "clock_out": str(row.clock_out_time) if row.clock_out_time else None,
                "location":  row.location or "Muscletech Fitness",
            })

        # ── Pattern signal for personality layer ──────────────────────
        pattern_signal = _compute_pattern_signal(
            visits_this_month, days_missed_this_month,
            streak, longest, total_checkins
        )

        # ── ASCII 30-day presence chart ────────────────────────────────
        ascii_chart = _build_ascii_chart(dates_present_set, today)

        # ── LLM reasoning — answers the member's actual question ───────
        data_block = (
            f"Visits this month: {visits_this_month}\n"
            f"Days missed this month: {days_missed_this_month}\n"
            f"Current streak: {streak} days\n"
            f"Longest streak in last 30 days: {longest} days\n"
            f"Last check-in: {last_checkin_raw}\n"
            f"Total check-ins ever: {total_checkins}\n"
            f"Dates present last 30 days: {checkins_last_30}\n"
            f"30-day chart (■=present □=absent): {ascii_chart}"
        )
        system_prompt = (
            "You are an attendance analyst for Muscletech Fitness gym in Hyderabad, India. "
            "Given raw attendance data and a member's question, produce a short (2-3 sentence) "
            "factual, warm, specific insight. Answer their actual question directly. "
            "If asked about weekday patterns, analyze the dates list to determine which days they visit. "
            "Do not use bullet points. Do not invent data."
        )
        user_content = (
            f"Member question: {user_query or 'Give me an overview of my recent attendance'}\n\n"
            f"Data:\n{data_block}"
        )
        try:
            analysis = await asyncio.to_thread(
                _call_groq, system_prompt, user_content, 200, 0.4
            )
        except Exception as exc:
            logger.warning(f"Attendance LLM call failed for {member_id}: {exc}")
            analysis = pattern_signal

        return {
            "analysis":                analysis,
            "visits_this_month":       visits_this_month,
            "days_missed_this_month":  days_missed_this_month,
            "current_streak":          streak,
            "longest_streak_30d":      longest,
            "last_checkin":            str(last_checkin_raw) if last_checkin_raw else None,
            "total_checkins":          total_checkins,
            "checkins_last_30":        checkins_last_30,
            "recent_logs":             recent_logs,
            "pattern_signal":          pattern_signal,
            "ascii_chart":             ascii_chart,
        }

    except Exception as e:
        logger.error(f"Attendance agent failed for {member_id}: {e}")
        return {
            "analysis": "Unable to load attendance data.",
            "visits_this_month": 0, "days_missed_this_month": 0,
            "current_streak": 0, "longest_streak_30d": 0,
            "last_checkin": None, "total_checkins": 0,
            "checkins_last_30": [], "recent_logs": [],
            "pattern_signal": "Unable to load attendance data.",
            "ascii_chart": "",
        }


def _compute_pattern_signal(
    visits: int, missed: int, streak: int, longest: int, total: int
) -> str:
    """Generate a coach-readable insight about attendance pattern."""
    if visits == 0:
        return "Has NOT visited at all this month. Be warm — ask what's going on, don't lecture."
    if streak >= 7:
        return f"On fire — {streak}-day streak! Celebrate this loudly and genuinely."
    if streak >= 4:
        return f"Good momentum — {streak}-day streak. Encourage them to push for a week."
    if visits >= 16:
        return f"Excellent month — {visits} visits. Acknowledge the consistency."
    if visits >= 10:
        return f"Solid month — {visits} visits. A positive word goes a long way."
    if missed > visits:
        return f"Missing more days ({missed}) than attending ({visits}). Raise this gently — ask what's happening."
    if total <= 5:
        return "New member. Be extra warm, encouraging, and build trust."
    return f"{visits} visits this month. Decent — encourage them to push a bit harder."


def _build_ascii_chart(dates_present: list, today: date) -> str:
    """
    Build a compact 30-day presence chart.
    Example: Apr 01  ■■□□■■■□□□■■□□■■■■□□■■■□□□■□□□
    ■ = present, □ = absent
    """
    thirty_ago = today - timedelta(days=29)
    dates_set = set(dates_present)
    bars = []
    for i in range(30):
        d = thirty_ago + timedelta(days=i)
        bars.append("■" if d in dates_set else "□")
    month_start = thirty_ago.strftime("%b %d")
    return f"{month_start}  {''.join(bars)}  {today.strftime('%b %d')}"