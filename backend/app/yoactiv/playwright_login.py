"""
Playwright Auto-Login for Yoactiv
==================================
Uses a persistent Chromium profile to defeat Cloudflare Turnstile.

WHY THIS WORKS:
  Previous approach used launch() + new_context() — Playwright adds
  --enable-automation flag which Cloudflare detects immediately.

  This version uses launch_persistent_context() with:
    - ignore_default_args=["--enable-automation"]  ← removes the flag
    - --disable-blink-features=AutomationControlled ← hides webdriver
    - A saved profile directory (yoactiv_profile/)  ← looks like real browser

FLOW:
  First run  → visible browser, you log in once, profile saved
  All future → headless with saved profile, no login page, no CAPTCHA
  Profile lasts until Yoactiv fully kills the session (~7 days)
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent / "cookies.json"
PROFILE_DIR  = Path(__file__).parent / "yoactiv_profile"   # persistent browser profile
BASE_URL     = os.environ.get("YOACTIV_BASE_URL", "https://backstage.yoactiv.com")
REQUIRED     = ["ASP.NET_SessionId", "AWSALB", "AWSALBCORS"]

# Confirmed selectors from live Yoactiv page inspection
USERNAME_SEL = 'input[name="txtbmail"]'
PASSWORD_SEL = 'input[name="txtbpwd"]'
BUTTON_SEL   = 'input[name="Button2"]'

# Chromium args that remove all automation signals
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-notifications",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

# These are the Playwright default args we must remove
REMOVE_ARGS = ["--enable-automation"]

# JavaScript injected into every page — hides navigator.webdriver
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
"""


async def auto_login() -> dict:
    """
    Main entry. Tries headless with saved profile first.
    Falls back to visible browser if session is dead.
    """
    PROFILE_DIR.mkdir(exist_ok=True)

    # If profile exists, try headless first
    if any(PROFILE_DIR.iterdir()):
        try:
            logger.info("Playwright: trying headless with saved profile...")
            return await _login(headless=True)
        except Exception as e:
            logger.warning(f"Headless failed ({e}), switching to visible browser...")

    # First time or session dead: visible browser, user logs in once
    return await _login(headless=False)


async def _login(headless: bool) -> dict:
    """Core login using persistent context."""
    from playwright.async_api import async_playwright

    username, password = _get_credentials()

    if not headless:
        _print_guided_instructions()

    async with async_playwright() as pw:
        # launch_persistent_context = real browser profile, not a throwaway context
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            args=STEALTH_ARGS + (["--start-maximized"] if not headless else []),
            ignore_default_args=REMOVE_ARGS,   # ← KEY: removes --enable-automation
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        # Inject stealth script on every new page
        await context.add_init_script(STEALTH_SCRIPT)

        page = context.pages[0] if context.pages else await context.new_page()

        logger.info(f"Playwright: navigating to {BASE_URL} (headless={headless})")
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2000)

        url = page.url
        logger.info(f"Playwright: current URL = {url}")

        # Already on dashboard — session still alive
        if "dashboardpro.aspx" in url:
            logger.info("Playwright: profile session still valid — on dashboard!")
            result = await _extract_and_save(context)
            await context.close()
            return result

        # If headless and not on dashboard, need visible browser
        if headless:
            await context.close()
            raise Exception("Session expired — needs guided login")

        # ── VISIBLE BROWSER PATH ──────────────────────────────────
        # Pre-fill credentials to help the user
        try:
            await page.wait_for_selector(USERNAME_SEL, timeout=8000)
            await page.fill(USERNAME_SEL, username)
            await page.fill(PASSWORD_SEL, password)
            print("\n  ✓ Email and password pre-filled.")
            print("  → Complete the CAPTCHA checkbox and click Login.\n")
        except Exception:
            print("\n  → Please fill in your email and password.\n")

        # Poll for dashboard — user logs in manually
        print("  Waiting for you to complete login", end="", flush=True)
        logged_in = False
        for i in range(180):
            await asyncio.sleep(1)
            try:
                current = page.url
            except Exception:
                break  # page closed
            if "dashboardpro.aspx" in current:
                logged_in = True
                break
            if i > 0 and i % 20 == 0:
                print(f"\n  Still waiting... ({180 - i}s left)", end="", flush=True)
            else:
                print(".", end="", flush=True)

        print()

        if not logged_in:
            await context.close()
            raise RuntimeError(
                "Timed out waiting for login. Please run again and log in within 3 minutes."
            )

        print("\n  ✅ Dashboard detected! Saving profile...")
        await page.wait_for_timeout(2000)   # let page settle

        result = await _extract_and_save(context)
        await context.close()

    print("  ✅ Profile saved to yoactiv_profile/")
    print("  ✅ Next sync will be fully automatic — no CAPTCHA!")
    print("=" * 60)
    print()
    return result


async def _extract_and_save(context) -> dict:
    """Extract 3 required cookies from context and save to cookies.json."""
    all_cookies = await context.cookies()
    cdict = {c["name"]: c["value"] for c in all_cookies}

    missing = [k for k in REQUIRED if k not in cdict]
    if missing:
        raise RuntimeError(f"Missing cookies after login: {missing}")

    fresh = {k: cdict[k] for k in REQUIRED}
    data = dict(fresh)
    data["_last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(COOKIES_FILE, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Cookies saved. SessionId prefix: {fresh['ASP.NET_SessionId'][:12]}")
    return fresh


def _get_credentials() -> tuple:
    u = os.environ.get("YOACTIV_USERNAME", "").strip()
    p = os.environ.get("YOACTIV_PASSWORD", "").strip()
    if not u or not p:
        raise ValueError("Set YOACTIV_USERNAME and YOACTIV_PASSWORD in .env")
    return u, p


def _print_guided_instructions():
    print()
    print("=" * 60)
    print("  GUIDED LOGIN — ONE-TIME SETUP")
    print("=" * 60)
    print()
    print("  A browser window is opening. This happens only once")
    print("  (or after ~7 days when the session fully expires).")
    print()
    print("  Steps:")
    print("  1. Email and password are pre-filled for you")
    print("  2. Tick the CAPTCHA checkbox")
    print("  3. Click Login")
    print("  4. Wait for the Yoactiv dashboard — then stop")
    print("     (we detect it and save automatically)")
    print()
    print("  You have 3 minutes. Opening browser now...")
    print("=" * 60)


async def ensure_valid_session() -> None:
    """Call at the top of every sync job."""
    from app.yoactiv.cookie_manager import (
        load_cookies, validate_cookies, CookieExpiredError
    )
    try:
        cookies = load_cookies()
        if validate_cookies(cookies):
            logger.debug("ensure_valid_session: cookies valid")
            return
        logger.warning("ensure_valid_session: cookies expired — auto-login starting")
    except CookieExpiredError:
        logger.warning("ensure_valid_session: no cookies — auto-login starting")

    await auto_login()
    logger.info("ensure_valid_session: complete")