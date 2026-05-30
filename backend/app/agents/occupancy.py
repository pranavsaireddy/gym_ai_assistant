# backend/app/agents/occupancy.py
"""
Occupancy Agent
===============
Makes a live on-demand request to Yoactiv's clientcheckins.aspx.
Members with an empty clock_out time are currently in the gym.
No scheduled sync needed — always real-time.
"""
import logging
from datetime import date
from app.yoactiv.session import get_session, safe_get, HTML_HEADERS

logger = logging.getLogger(__name__)

BASE_URL = "https://backstage.yoactiv.com"


async def run_occupancy() -> dict:
    """
    Returns:
    {
        count: int,              # members currently in gym
        source: str,             # 'live' | 'error'
        as_of: str,              # timestamp string
        peak_signal: str,        # 'quiet' | 'moderate' | 'busy' | 'unknown'
        suggestion: str,         # coach-readable signal
    }
    """
    from datetime import datetime
    today_str = date.today().strftime("%d-%m-%Y")
    as_of = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        session = get_session()

        # clientcheckins with today's date range
        url = f"/clientcheckins.aspx?frm={today_str}&tto={today_str}"
        response = safe_get(session, url, headers=HTML_HEADERS, delay=0.0)

        html = response.text

        # Detect session expiry (safe_get already checks, but double-guard)
        if len(html) < 5000 or "Session-Out" in html or "ReturnUrl=" in html:
            raise Exception("Session expired during occupancy check")

        # Parse — count rows where clock_out is empty (member still inside)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        count = 0
        for row in soup.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 6 and cols[0].isdigit():
                # Clock-out is column index 5 in clientcheckins
                clock_out = cols[5].strip()
                if not clock_out or clock_out in ("", "-", "—"):
                    count += 1

        peak_signal, suggestion = _classify_occupancy(count)

        return {
            "count":       count,
            "source":      "live",
            "as_of":       as_of,
            "peak_signal": peak_signal,
            "suggestion":  suggestion,
        }

    except Exception as e:
        logger.warning(f"Occupancy agent failed: {e}")
        return {
            "count":       None,
            "source":      "error",
            "as_of":       as_of,
            "peak_signal": "unknown",
            "suggestion":  "Gym occupancy data is temporarily unavailable.",
        }


def _classify_occupancy(count: int) -> tuple[str, str]:
    if count <= 8:
        return (
            "quiet",
            f"Only {count} people in the gym right now — great time to come in, no waiting for equipment.",
        )
    if count <= 25:
        return (
            "moderate",
            f"{count} people in the gym — comfortably busy, all equipment accessible.",
        )
    if count <= 40:
        return (
            "busy",
            f"{count} people in the gym right now — might be some wait for popular equipment.",
        )
    return (
        "packed",
        f"Gym is quite full right now ({count} people). If you can, early morning or post-9PM is quieter.",
    )