"""
Yoactiv Cookie Agent
=====================
Runs on the gym PC (or your PC for testing).
Reads Yoactiv cookies from Edge/Chrome and pushes them to the backend.

Setup (one time):
  1. pip install requests pywin32 pycryptodome
  2. Set BACKEND_URL and COOKIE_SECRET in the CONFIG section below
  3. Run: python cookie_agent.py            (manual test)
  4. Run: python cookie_agent.py --install  (installs Windows Task Scheduler job)

After --install: runs automatically every 30 minutes, even after reboot.
"""
import base64
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# CONFIG — set these before running
# ══════════════════════════════════════════════════════════════
BACKEND_URL  = "http://localhost:8000"   # change to Railway URL after deployment
COOKIE_SECRET = os.environ.get("COOKIE_SECRET", "changeme-set-in-env")
YOACTIV_DOMAIN = "backstage.yoactiv.com"
REQUIRED = ["ASP.NET_SessionId", "AWSALB", "AWSALBCORS"]
PUSH_INTERVAL_MINUTES = 30
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "cookie_agent.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def get_browser_paths() -> list[tuple[str, Path]]:
    """Find installed browser profile directories."""
    home = Path.home()
    candidates = [
        ("Edge",   home / "AppData/Local/Microsoft/Edge/User Data/Default"),
        ("Chrome", home / "AppData/Local/Google/Chrome/User Data/Default"),
        ("Brave",  home / "AppData/Local/BraveSoftware/Brave-Browser/User Data/Default"),
    ]
    found = []
    for name, profile in candidates:
        db = profile / "Network" / "Cookies"
        if not db.exists():
            db = profile / "Cookies"
        if db.exists():
            found.append((name, profile))
    return found


def get_encryption_key(profile_path: Path) -> bytes:
    """Get the AES key used to encrypt cookies. Decrypted via Windows DPAPI."""
    import win32crypt

    local_state = profile_path.parent / "Local State"
    with open(local_state, "r", encoding="utf-8") as f:
        state = json.load(f)

    enc_key_b64 = state["os_crypt"]["encrypted_key"]
    enc_key = base64.b64decode(enc_key_b64)
    if enc_key[:5] == b"DPAPI":
        enc_key = enc_key[5:]
    _, key = win32crypt.CryptUnprotectData(enc_key, None, None, None, 0)
    return key


def decrypt_cookie(encrypted_value: bytes, key: bytes) -> str | None:
    """Decrypt a Chrome/Edge AES-GCM encrypted cookie value."""
    if not encrypted_value:
        return None
    if encrypted_value[:3] in (b"v10", b"v11"):
        try:
            from Crypto.Cipher import AES
            iv = encrypted_value[3:15]
            payload = encrypted_value[15:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt(payload)
            return decrypted[:-16].decode("utf-8", errors="replace")
        except Exception:
            return None
    else:
        try:
            import win32crypt
            _, val = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)
            return val.decode("utf-8", errors="replace")
        except Exception:
            return None


def extract_cookies() -> dict | None:
    """
    Read Yoactiv cookies from the first browser that has them.
    Returns dict with 3 required cookies, or None if not found.
    """
    browsers = get_browser_paths()
    if not browsers:
        logger.error("No Chrome or Edge found on this PC")
        return None

    for browser_name, profile_path in browsers:
        try:
            key = get_encryption_key(profile_path)

            # Copy DB to temp — browser locks the original
            db_path = profile_path / "Network" / "Cookies"
            if not db_path.exists():
                db_path = profile_path / "Cookies"

            tmp = tempfile.mktemp(suffix=".db")
            shutil.copy2(str(db_path), tmp)

            try:
                conn = sqlite3.connect(tmp)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE ?",
                    (f"%{YOACTIV_DOMAIN}%",)
                )
                rows = cursor.fetchall()
                conn.close()
            finally:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass

            cookies = {}
            for name, enc_val in rows:
                val = decrypt_cookie(enc_val, key)
                if val:
                    cookies[name] = val

            missing = [k for k in REQUIRED if k not in cookies]
            if missing:
                logger.info(f"{browser_name}: Yoactiv cookies missing {missing} — not logged in?")
                continue

            result = {k: cookies[k] for k in REQUIRED}
            logger.info(
                f"Extracted from {browser_name} — "
                f"SessionId: {result['ASP.NET_SessionId'][:12]}..."
            )
            return result

        except ImportError:
            logger.error("Missing packages. Run: pip install pywin32 pycryptodome")
            return None
        except Exception as e:
            logger.debug(f"{browser_name}: extraction error — {e}")
            continue

    logger.warning("No Yoactiv cookies found in any browser. Is Yoactiv open and logged in?")
    return None


def push_cookies(cookies: dict) -> bool:
    """POST cookies to the backend /internal/refresh-cookies endpoint."""
    import requests

    url = f"{BACKEND_URL.rstrip('/')}/internal/refresh-cookies"
    payload = {
        "cookies": cookies,
        "pushed_at": datetime.now().isoformat(),
        "pushed_from": os.environ.get("COMPUTERNAME", "unknown_pc"),
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "X-Cookie-Secret": COOKIE_SECRET,
                "Content-Type": "application/json",
            },
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"Push successful — backend says: {data.get('message', 'ok')}")
            return True
        elif resp.status_code == 401:
            logger.error("Push rejected — wrong COOKIE_SECRET. Check both sides.")
            return False
        else:
            logger.error(f"Push failed — HTTP {resp.status_code}: {resp.text[:200]}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot reach backend at {url}. Is the server running?")
        return False
    except Exception as e:
        logger.error(f"Push error: {e}")
        return False


def run_once() -> bool:
    """Extract cookies and push to backend. Returns True if successful."""
    logger.info("─" * 50)
    logger.info(f"Cookie agent running — target: {BACKEND_URL}")

    cookies = extract_cookies()
    if not cookies:
        logger.warning("No cookies extracted — skipping push")
        return False

    ok = push_cookies(cookies)
    if ok:
        logger.info("Done ✓")
    return ok


def run_loop():
    """Run continuously, pushing every PUSH_INTERVAL_MINUTES minutes."""
    logger.info(f"Cookie agent started — pushing every {PUSH_INTERVAL_MINUTES} minutes")
    logger.info(f"Backend: {BACKEND_URL}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            logger.info("Stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        logger.info(f"Next push in {PUSH_INTERVAL_MINUTES} minutes...")
        time.sleep(PUSH_INTERVAL_MINUTES * 60)


def install_task_scheduler():
    """
    Register this script as a Windows Task Scheduler job.
    Runs every 30 minutes, starts on login, runs silently.
    """
    import subprocess

    script_path = Path(__file__).resolve()
    python_path = sys.executable

    # Build the schtasks command
    task_name = "YoactivCookieAgent"
    cmd = (
        f'schtasks /create /tn "{task_name}" '
        f'/tr "\\"{python_path}\\" \\"{script_path}\\" --once" '
        f'/sc MINUTE /mo {PUSH_INTERVAL_MINUTES} '
        f'/ru SYSTEM '
        f'/rl HIGHEST '
        f'/f'   # /f = force overwrite if exists
    )

    print(f"Registering Task Scheduler job: {task_name}")
    print(f"Script: {script_path}")
    print(f"Python: {python_path}")
    print(f"Interval: every {PUSH_INTERVAL_MINUTES} minutes")
    print()

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Task Scheduler job created successfully!")
        print(f"   The cookie agent will now run every {PUSH_INTERVAL_MINUTES} minutes automatically.")
        print()
        print("To view in Task Scheduler: Win+R → taskschd.msc → Task Scheduler Library")
        print(f"To remove: schtasks /delete /tn \"{task_name}\" /f")
    else:
        print(f"❌ Failed to create task: {result.stderr}")
        print()
        print("Try running this script as Administrator (right-click → Run as Admin)")


def check_status():
    """Print current status — useful for debugging."""
    print()
    print("Cookie Agent Status Check")
    print("=" * 50)
    print(f"Backend URL:    {BACKEND_URL}")
    print(f"Secret set:     {'Yes' if COOKIE_SECRET != 'changeme-set-in-env' else 'NO — set COOKIE_SECRET env var'}")
    print()

    # Check dependencies
    deps_ok = True
    try:
        import win32crypt
        print("✅ pywin32 installed")
    except ImportError:
        print("❌ pywin32 missing — run: pip install pywin32")
        deps_ok = False

    try:
        from Crypto.Cipher import AES
        print("✅ pycryptodome installed")
    except ImportError:
        print("❌ pycryptodome missing — run: pip install pycryptodome")
        deps_ok = False

    try:
        import requests
        print("✅ requests installed")
    except ImportError:
        print("❌ requests missing — run: pip install requests")
        deps_ok = False

    if not deps_ok:
        print()
        print("Install missing packages:")
        print("  pip install pywin32 pycryptodome requests")
        return

    print()

    # Check browsers
    browsers = get_browser_paths()
    if browsers:
        print(f"✅ Browsers found: {[b[0] for b in browsers]}")
    else:
        print("❌ No Chrome or Edge found")

    print()

    # Try extraction
    print("Testing cookie extraction...")
    cookies = extract_cookies()
    if cookies:
        print(f"✅ Yoactiv cookies found!")
        for k, v in cookies.items():
            print(f"   {k}: {v[:16]}...")
    else:
        print("❌ No Yoactiv cookies — log into backstage.yoactiv.com in Edge first")

    print()

    # Test backend connection
    import requests as req
    try:
        r = req.get(f"{BACKEND_URL}/health", timeout=5)
        if r.status_code == 200:
            print(f"✅ Backend reachable at {BACKEND_URL}")
        else:
            print(f"⚠️  Backend returned HTTP {r.status_code}")
    except Exception:
        print(f"❌ Cannot reach backend at {BACKEND_URL}")
        print("   Make sure the FastAPI server is running (uvicorn app.main:app)")

    print()


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--install" in args:
        install_task_scheduler()
    elif "--once" in args:
        # Used by Task Scheduler — run once and exit
        run_once()
    elif "--status" in args:
        check_status()
    elif "--loop" in args:
        run_loop()
    else:
        # Default: status check + one push
        print("Running cookie agent (one-shot)...")
        print("Use --loop to run continuously, --install to add to Task Scheduler")
        print()
        check_status()
        print("─" * 50)
        print("Attempting push...")
        run_once()
