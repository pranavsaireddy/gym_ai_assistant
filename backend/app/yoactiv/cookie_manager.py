"""
Cookie manager for Yoactiv session authentication.

Yoactiv uses JavaScript-based login that cannot be replicated with raw httpx.
Solution: Manual cookie injection from authenticated browser session.

Usage:
    from app.yoactiv.cookie_manager import get_valid_cookies, CookieExpiredError

    try:
        cookies = get_valid_cookies()
    except CookieExpiredError as e:
        # Alert admin to refresh cookies.json
        logger.error(str(e))
"""
import json
import logging
import httpx
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Path to cookies file — sits next to this module
COOKIES_FILE = Path(__file__).parent / "cookies.json"
BASE_URL = "https://backstage.yoactiv.com"
REQUIRED_COOKIES = ["ASP.NET_SessionId", "AWSALB", "AWSALBCORS"]

# A real Yoactiv page is always >15KB. Login page is ~5KB.
# If response is smaller, session is dead.
MIN_VALID_PAGE_SIZE = 15_000


class CookieExpiredError(Exception):
    """
    Raised when Yoactiv cookies are missing, unpasted, or expired.
    When caught, alert admin to update cookies.json.
    """
    pass


def load_cookies() -> dict:
    """
    Load cookies from cookies.json file.
    Raises CookieExpiredError if file missing or values not pasted.
    """
    if not COOKIES_FILE.exists():
        raise CookieExpiredError(
            f"cookies.json not found at {COOKIES_FILE}. "
            "Create it by copying your Yoactiv browser cookies. "
            "See documentation: Yoactiv_Integration_Architecture.docx Section 2."
        )

    with open(COOKIES_FILE, "r") as f:
        try:
            cookies = json.load(f)
        except json.JSONDecodeError as e:
            raise CookieExpiredError(f"cookies.json is not valid JSON: {e}")

    # Check all required cookies are present and not placeholder values
    missing = []
    for key in REQUIRED_COOKIES:
        val = cookies.get(key, "")
        if not val or val.strip() == "paste_your_value_here" or val.strip() == "":
            missing.append(key)

    if missing:
        raise CookieExpiredError(
            f"cookies.json is missing or has unpasted values for: {missing}. "
            "Log into backstage.yoactiv.com → F12 → Application → Cookies → "
            "Copy ASP.NET_SessionId, AWSALB, AWSALBCORS into cookies.json."
        )

    # Return only the actual cookie values (exclude metadata like _last_updated)
    return {k: cookies[k] for k in REQUIRED_COOKIES}


def validate_cookies(cookies: dict) -> bool:
    """
    Test cookies by loading the Yoactiv dashboard.
    Returns True if session is valid, False if expired.

    We check page size because:
    - Valid dashboard: 30,000–200,000 bytes
    - Login page (expired session): ~5,000 bytes
    """
    try:
        with httpx.Client(
            base_url=BASE_URL,
            cookies=cookies,
            follow_redirects=True,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Encoding": "gzip, deflate",
            }
        ) as client:
            resp = client.get("/dashboardpro.aspx")

            is_valid = (
                resp.status_code == 200
                and len(resp.text) >= MIN_VALID_PAGE_SIZE
                and "backstage.yoactiv.com/dashboardpro.aspx" in str(resp.url)
            )

            if not is_valid:
                logger.warning(
                    f"Cookie validation FAILED — "
                    f"status={resp.status_code}, "
                    f"size={len(resp.text)} bytes, "
                    f"url={resp.url}"
                )
            else:
                logger.info(f"Cookie validation OK — dashboard loaded ({len(resp.text)} bytes)")

            return is_valid

    except httpx.TimeoutException:
        logger.error("Cookie validation timed out — Yoactiv may be slow")
        return False
    except Exception as e:
        logger.error(f"Cookie validation error: {e}")
        return False


def get_valid_cookies() -> dict:
    """
    Load and validate cookies in one call.
    This is the main entry point used by session.py and sync_engine.py.

    Raises CookieExpiredError if cookies are missing, invalid, or expired.
    Returns dict with all 3 cookies if valid.
    """
    cookies = load_cookies()           # raises CookieExpiredError if not pasted

    if not validate_cookies(cookies):  # hits Yoactiv to verify
        raise CookieExpiredError(
            "Yoactiv session cookies have expired. "
            "Log into backstage.yoactiv.com in your browser, "
            "go to F12 → Application → Cookies → backstage.yoactiv.com, "
            "copy ASP.NET_SessionId, AWSALB, AWSALBCORS into cookies.json, "
            "then trigger a manual sync via POST /admin/sync/all."
        )

    return cookies


def get_cookies_age_warning() -> str | None:
    """
    Returns a warning string if cookies haven't been updated recently,
    or None if _last_updated is recent or not present.
    Used to proactively warn before cookies expire.
    """
    if not COOKIES_FILE.exists():
        return None
    try:
        with open(COOKIES_FILE) as f:
            data = json.load(f)
        last_updated_str = data.get("_last_updated", "")
        if not last_updated_str or last_updated_str == "paste the date you updated this e.g. 2026-04-12 20:00":
            return None

        # Try to parse date
        for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d"]:
            try:
                last_updated = datetime.strptime(last_updated_str.strip(), fmt)
                age_hours = (datetime.now() - last_updated).total_seconds() / 3600
                if age_hours > 18:
                    return (
                        f"⚠️  Yoactiv cookies were last updated {age_hours:.0f} hours ago "
                        f"({last_updated_str}). Consider refreshing them before the next sync."
                    )
                return None
            except ValueError:
                continue
    except Exception:
        pass
    return None
