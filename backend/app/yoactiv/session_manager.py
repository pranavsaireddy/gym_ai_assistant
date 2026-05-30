"""
Yoactiv Session Manager
========================
Called before every sync job. Ensures valid cookies are available.

Flow:
  1. Check cookies.json -- valid? Done (instant, most common path)
  2. Load from Supabase (written by gym PC cookie agent)
  3. If still expired -- print instructions, raise error

Also provides run_keepalive() — called every 15 min by scheduler
to prevent ASP.NET_SessionId from timing out.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent / "cookies.json"
REQUIRED = ["ASP.NET_SessionId", "AWSALB", "AWSALBCORS"]


async def ensure_valid_session() -> None:
    """
    Main entry point — called at top of every sync job.
    Raises RuntimeError if no valid session can be obtained.
    """
    from app.yoactiv.cookie_manager import load_cookies, validate_cookies, CookieExpiredError

    # Fast path — most common case
    try:
        if validate_cookies(load_cookies()):
            logger.debug("Session valid")
            return
    except CookieExpiredError:
        pass

    logger.warning("Session expired — loading from Supabase")

    # Load from Supabase (written by gym PC cookie agent)
    from app.yoactiv.cookie_store import load_cookies_from_db
    db_cookies = await load_cookies_from_db()

    if db_cookies and validate_cookies(db_cookies):
        _write_cookies_file(db_cookies)
        logger.info("Session restored from Supabase")
        return

    # Cannot recover
    _print_instructions()
    raise RuntimeError(
        "Yoactiv session expired and Supabase has no fresh cookies. "
        "Make sure the cookie agent is running on the gym PC and "
        "Yoactiv is open and logged in there."
    )


async def run_keepalive() -> None:
    """
    Ping Yoactiv every 15 min to keep ASP.NET_SessionId alive.
    If it detects expiry, reloads from Supabase automatically.
    """
    from app.yoactiv.cookie_manager import load_cookies, validate_cookies, CookieExpiredError
    from app.yoactiv.session import get_session

    try:
        cookies = load_cookies()
        if not validate_cookies(cookies):
            logger.warning("Keepalive: session expired — reloading from Supabase")
            await ensure_valid_session()
            return
    except CookieExpiredError:
        await ensure_valid_session()
        return

    # Make a tiny request to reset the 30-min idle timer
    try:
        session = get_session()
        resp = session.get("/dashboardpro.aspx")
        logger.debug(f"Keepalive: OK ({len(resp.text)} bytes)")
    except CookieExpiredError:
        logger.warning("Keepalive: session died on ping — reloading from Supabase")
        await ensure_valid_session()
    except Exception as e:
        logger.debug(f"Keepalive ping error (non-fatal): {e}")


def _write_cookies_file(cookies: dict) -> None:
    """Write cookies dict to cookies.json."""
    data = {k: cookies[k] for k in REQUIRED if k in cookies}
    data["_last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(COOKIES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _print_instructions():
    print()
    print("=" * 55)
    print("  YOACTIV SESSION EXPIRED")
    print("=" * 55)
    print()
    print("  The cookie agent on the gym PC hasn't pushed")
    print("  fresh cookies recently.")
    print()
    print("  Fix:")
    print("  1. Go to gym PC (or your PC while testing)")
    print("  2. Open Chrome -> log into backstage.yoactiv.com")
    print("  3. Run: python cookie_agent.py --once")
    print("  4. Retry the sync")
    print()
    print("=" * 55)
