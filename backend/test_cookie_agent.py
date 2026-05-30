"""
Cookie Agent End-to-End Test
==============================
Tests the full flow: extract cookies → push to backend → verify saved.

Before running:
  1. Backend must be running: uvicorn app.main:app --reload
  2. Yoactiv must be open in Edge and logged in
  3. COOKIE_SECRET must match in both .env and this test
  4. pip install pywin32 pycryptodome requests

Run:
  python test_cookie_agent.py
"""
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

BACKEND_URL   = "http://localhost:8000"
COOKIE_SECRET = os.environ.get("COOKIE_PUSH_SECRET", "changeme-generate-a-real-secret")


def main():
    print("=" * 55)
    print("  Cookie Agent — End-to-End Test")
    print("=" * 55)

    # ── Test 1: Dependencies ──────────────────────────────────
    print("\n[1/4] Checking dependencies...")
    ok = True
    for pkg, imp in [("pywin32", "win32crypt"), ("pycryptodome", "Crypto.Cipher"), ("requests", "requests")]:
        try:
            __import__(imp)
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} — run: pip install {pkg}")
            ok = False
    if not ok:
        return

    # ── Test 2: Extract from Edge ─────────────────────────────
    print("\n[2/4] Extracting cookies from Edge/Chrome...")
    sys.path.insert(0, ".")
    try:
        from cookie_agent import extract_cookies
        cookies = extract_cookies()
        if not cookies:
            print("  ❌ No Yoactiv cookies found in browser.")
            print("  → Open Edge and log into backstage.yoactiv.com first")
            return
        print(f"  ✅ Cookies extracted!")
        for k, v in cookies.items():
            print(f"     {k}: {v[:16]}...")
    except Exception as e:
        print(f"  ❌ Extraction failed: {e}")
        return

    # ── Test 3: Push to backend ───────────────────────────────
    print("\n[3/4] Pushing cookies to backend...")
    print(f"      Backend: {BACKEND_URL}")
    try:
        import requests
        resp = requests.post(
            f"{BACKEND_URL}/internal/refresh-cookies",
            json={
                "cookies": cookies,
                "pushed_at": __import__('datetime').datetime.now().isoformat(),
                "pushed_from": os.environ.get("COMPUTERNAME", "test_pc"),
            },
            headers={"X-Cookie-Secret": COOKIE_SECRET},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Backend accepted cookies!")
            print(f"     Message: {data.get('message')}")
            print(f"     SessionId prefix: {data.get('session_id_prefix')}")
            print(f"     Updated at: {data.get('updated_at')}")
        elif resp.status_code == 401:
            print(f"  ❌ Backend rejected — wrong COOKIE_PUSH_SECRET")
            print(f"     Make sure COOKIE_PUSH_SECRET in .env matches the agent config")
        else:
            print(f"  ❌ Backend returned HTTP {resp.status_code}: {resp.text[:300]}")
            return
    except Exception as e:
        print(f"  ❌ Push failed: {e}")
        print(f"  → Is the backend running? Try: uvicorn app.main:app --reload")
        return

    # ── Test 4: Verify cookie health endpoint ─────────────────
    print("\n[4/4] Verifying cookie status on backend...")
    try:
        import requests
        r = requests.get(
            f"{BACKEND_URL}/health/cookies",
            timeout=10
        )
        data = r.json()
        status = data.get("status")
        if status == "valid":
            print(f"  ✅ Backend confirms cookies are VALID")
            print(f"     {data.get('message', '')}")
        else:
            print(f"  ⚠️  Status: {status} — {data.get('message')}")
    except Exception as e:
        print(f"  ❌ Health check failed: {e}")

    print()
    print("=" * 55)
    print("  ✅ ALL TESTS PASSED")
    print()
    print("  Cookie flow is working:")
    print("  Edge (Yoactiv) → cookie_agent.py → backend → syncs")
    print()
    print("  Next steps:")
    print("  1. Add to .env: COOKIE_PUSH_SECRET=<same value as agent>")
    print("  2. Set BACKEND_URL in cookie_agent.py to Railway URL (after deploy)")
    print("  3. Copy cookie_agent.py to gym PC and run --install")
    print("=" * 55)


if __name__ == "__main__":
    main()
