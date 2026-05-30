"""
Internal API routes — not exposed to members or staff.
Used for the cookie agent running on the gym PC.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent.parent / "yoactiv" / "cookies.json"
REQUIRED = ["ASP.NET_SessionId", "AWSALB", "AWSALBCORS"]


class CookiePushRequest(BaseModel):
    cookies: dict
    pushed_at: str = ""
    pushed_from: str = "unknown"


@router.post("/refresh-cookies")
async def refresh_cookies(body: CookiePushRequest, request: Request):
    """
    Receive fresh Yoactiv cookies from the gym PC cookie agent.
    Protected by X-Cookie-Secret header.
    """
    # Validate secret
    secret = request.headers.get("X-Cookie-Secret", "")
    if secret != settings.COOKIE_PUSH_SECRET:
        logger.warning(f"Rejected cookie push — wrong secret from {body.pushed_from}")
        raise HTTPException(status_code=401, detail="Invalid secret")

    # Validate all required cookies are present
    missing = [k for k in REQUIRED if k not in body.cookies]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required cookies: {missing}"
        )

    # Save to cookies.json
    cookie_data = {k: body.cookies[k] for k in REQUIRED}
    cookie_data["_last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    cookie_data["_pushed_from"] = body.pushed_from

    with open(COOKIES_FILE, "w") as f:
        json.dump(cookie_data, f, indent=2)

    logger.info(
        f"Cookies updated from {body.pushed_from} — "
        f"SessionId: {cookie_data['ASP.NET_SessionId'][:12]}..."
    )

    # Also save to Supabase for persistence across restarts
    try:
        from app.yoactiv.cookie_store import save_cookies_to_db
        await save_cookies_to_db(cookie_data)
    except Exception as e:
        logger.warning(f"Supabase save failed (non-fatal): {e}")

    return {
        "message": "Cookies updated successfully",
        "pushed_from": body.pushed_from,
        "session_id_prefix": cookie_data["ASP.NET_SessionId"][:12],
        "updated_at": cookie_data["_last_updated"],
    }


@router.get("/cookie-status")
async def cookie_status(request: Request):
    """Check current cookie status. Protected by secret."""
    secret = request.headers.get("X-Cookie-Secret", "")
    if secret != settings.COOKIE_PUSH_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    if not COOKIES_FILE.exists():
        return {"status": "missing", "message": "No cookies.json found"}

    with open(COOKIES_FILE) as f:
        data = json.load(f)

    from app.yoactiv.cookie_manager import validate_cookies, CookieExpiredError
    try:
        from app.yoactiv.cookie_manager import load_cookies
        cookies = load_cookies()
        is_valid = validate_cookies(cookies)
    except CookieExpiredError:
        is_valid = False

    return {
        "status": "valid" if is_valid else "expired",
        "last_updated": data.get("_last_updated", "unknown"),
        "pushed_from": data.get("_pushed_from", "unknown"),
        "session_id_prefix": data.get("ASP.NET_SessionId", "")[:12],
    }
