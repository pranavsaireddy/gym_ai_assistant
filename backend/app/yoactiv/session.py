"""
Authenticated httpx session for Yoactiv requests.

All requests use cookies injected from cookies.json.
Rate limiting is enforced to be polite to Yoactiv's servers.
"""
import time
import json
import logging
import httpx
from .cookie_manager import get_valid_cookies, CookieExpiredError

logger = logging.getLogger(__name__)

BASE_URL = "https://backstage.yoactiv.com"

# ── Shared headers ────────────────────────────────────────────
# Accept-Encoding deliberately excludes 'br' (Brotli) — httpx needs
# the brotli package to decode it. gzip works natively and Yoactiv
# supports it. Tested and confirmed working.
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
    ),
    "Accept-Encoding": "gzip, deflate",   # NO 'br' — avoids Brotli decode errors
    "Accept-Language": "en-US,en;q=0.9",
}

HTML_HEADERS = {
    **BASE_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": f"{BASE_URL}/dashboardpro.aspx",
}

API_HEADERS = {
    **BASE_HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/memshiplist.aspx",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}

# ── Page size thresholds ──────────────────────────────────────
# Confirmed through testing:
#   Login page (expired session): ~5,000–7,000 bytes
#   Real data pages:              30,000–400,000 bytes
MIN_REAL_PAGE_SIZE = 15_000


def _is_session_dead(text: str) -> bool:
    """Detect if Yoactiv returned a session-expired response."""
    dead_markers = [
        "Session-Out",
        "txtUserName",        # login form field
        "btnLogin",           # login button
        "Please login",
        "session has expired",
    ]
    text_lower = text.lower()
    return any(m.lower() in text_lower for m in dead_markers)


def get_session() -> httpx.Client:
    """
    Build and return an authenticated httpx.Client.
    Validates cookies before returning — raises CookieExpiredError if invalid.

    Usage:
        session = get_session()
        resp = session.get("/some-page.aspx", headers=HTML_HEADERS)
    """
    cookies = get_valid_cookies()   # raises CookieExpiredError if invalid
    return httpx.Client(
        base_url=BASE_URL,
        cookies=cookies,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=10.0),
        headers=BASE_HEADERS,
    )


def safe_get(session: httpx.Client, url: str, headers: dict = None, delay: float = 0.3) -> httpx.Response:
    """
    GET a Yoactiv page with rate limiting and session validation.

    Args:
        session:  authenticated httpx.Client from get_session()
        url:      relative URL e.g. "/memviewatt.aspx?typ=1&yr=2026&mth=04"
        headers:  use HTML_HEADERS (default) or custom
        delay:    seconds to wait before request (rate limiting)

    Returns:
        httpx.Response with confirmed real page content

    Raises:
        CookieExpiredError: if page is the login page (session dead)
        Exception: for HTTP errors or network issues
    """
    time.sleep(delay)
    resp = session.get(url, headers=headers or HTML_HEADERS)

    if resp.status_code != 200:
        raise Exception(f"GET {url} → HTTP {resp.status_code}")

    if _is_session_dead(resp.text):
        raise CookieExpiredError(f"Session expired detected on GET {url} — login markers found in response")

    if len(resp.text) < MIN_REAL_PAGE_SIZE:
        raise CookieExpiredError(
            f"Response too small ({len(resp.text)} bytes) for {url} — "
            f"expected >{MIN_REAL_PAGE_SIZE} bytes. Session likely expired."
        )

    return resp


def safe_post(session: httpx.Client, url: str, payload: dict, delay: float = 0.3) -> dict:
    """
    POST to a Yoactiv JSON API endpoint with rate limiting and session validation.

    Args:
        session:  authenticated httpx.Client from get_session()
        url:      relative URL e.g. "/autofill.asmx/getClientDetails"
        payload:  dict to send as JSON body
        delay:    seconds to wait before request (rate limiting)

    Returns:
        Parsed JSON response dict

    Raises:
        CookieExpiredError: if response contains Session-Out
        Exception: for HTTP errors
    """
    time.sleep(delay)
    resp = session.post(
        url,
        content=json.dumps(payload),
        headers=API_HEADERS,
    )

    if resp.status_code == 401:
        raise CookieExpiredError(f"POST {url} → 401 Unauthorized — cookies invalid or expired")

    if resp.status_code != 200:
        raise Exception(f"POST {url} → HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except Exception:
        raise Exception(f"POST {url} returned non-JSON: {resp.text[:200]}")

    # Check for session expiry inside the response body
    d_field = str(data.get("d", ""))
    if "Session-Out" in d_field:
        raise CookieExpiredError(f"POST {url} → Session-Out in response body — cookies expired")

    return data
