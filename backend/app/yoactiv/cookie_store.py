"""
Cookie Store — persists Yoactiv cookies in Supabase.

On server restart, loads cookies from DB instead of needing
a new login. Works on Railway/Render deployment.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

TABLE = "yoactiv_session"   # will create if not exists
COOKIE_KEY = "main_session"


async def save_cookies_to_db(cookies: dict) -> None:
    """Save cookies to Supabase for persistence across restarts."""
    try:
        from app.database import AsyncSessionLocal
        from sqlalchemy import text

        # Ensure table exists
        async with AsyncSessionLocal() as db:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS yoactiv_session (
                    key VARCHAR(50) PRIMARY KEY,
                    cookies_json TEXT NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))

            await db.execute(text("""
                INSERT INTO yoactiv_session (key, cookies_json, updated_at)
                VALUES (:key, :val, NOW())
                ON CONFLICT (key) DO UPDATE
                SET cookies_json = :val, updated_at = NOW()
            """), {"key": COOKIE_KEY, "val": json.dumps(cookies)})

            await db.commit()
        logger.info("Cookies saved to Supabase")
    except Exception as e:
        logger.warning(f"Could not save cookies to DB (non-fatal): {e}")


async def load_cookies_from_db() -> dict | None:
    """Load cookies from Supabase. Returns None if not found."""
    try:
        from app.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT cookies_json FROM yoactiv_session WHERE key = :key"),
                {"key": COOKIE_KEY}
            )
            row = result.fetchone()
            if row:
                cookies = json.loads(row[0])
                logger.info("Cookies loaded from Supabase")
                return cookies
        return None
    except Exception as e:
        logger.debug(f"Could not load cookies from DB: {e}")
        return None
