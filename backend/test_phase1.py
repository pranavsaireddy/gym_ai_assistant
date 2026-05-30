"""
Phase 1 First Run Test
======================
Run this ONCE after setup to verify everything works end-to-end.

Before running:
  1. pip install -r requirements.txt
  2. Copy .env.example to .env and fill in DATABASE_URL, GROQ_API_KEY, JWT_SECRET_KEY
  3. Update cookies.json with your Yoactiv browser cookies
  4. Run: python test_phase1.py

What this tests:
  1. Cookies valid (hits Yoactiv dashboard)
  2. getClientDetails works (Pranav Sai Reddy, mid=2587500)
  3. getfullsrc works (search for 'pranav')
  4. memsvsess scraper works (Pranav's attendance)
  5. Database connection works (Supabase)
  6. Full member discovery (all 398 members)
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

TEST_MEMBER_ID = "2587500"
TEST_BILL_ID   = "6230391"


def test_cookies():
    print("\n[1/6] Testing Yoactiv cookies...")
    from app.yoactiv.cookie_manager import get_valid_cookies, CookieExpiredError
    try:
        cookies = get_valid_cookies()
        print(f"  ✅ Cookies valid — ASP.NET_SessionId: {cookies['ASP.NET_SessionId'][:12]}...")
        return True
    except CookieExpiredError as e:
        print(f"  ❌ Cookie error: {e}")
        return False


def test_get_client_details():
    print("\n[2/6] Testing getClientDetails (Pranav, mid=2587500)...")
    from app.yoactiv.api import get_client_details
    try:
        details = get_client_details(TEST_MEMBER_ID)
        print(f"  ✅ getClientDetails OK: {details}")
        assert details["status"], "Status field is empty"
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_getfullsrc():
    print("\n[3/6] Testing getfullsrc (search 'pranav')...")
    from app.yoactiv.api import discover_all_members
    from app.yoactiv.session import get_session, safe_post
    import re
    from bs4 import BeautifulSoup
    try:
        session = get_session()
        data = safe_post(session, "/autofill.asmx/getfullsrc", {"src": "pranav", "typ": "1"})
        raw_html = data.get("d", "")
        soup = BeautifulSoup(raw_html, "html.parser")
        links = soup.find_all("a", href=re.compile(r"mid=\d+"))
        print(f"  ✅ getfullsrc OK: found {len(links)} members for 'pranav'")
        for link in links:
            print(f"    → {link.get_text(strip=True)}")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_attendance_scraper():
    print("\n[4/6] Testing memsvsess attendance scraper...")
    from app.yoactiv.scraper import scrape_member_attendance
    try:
        records = scrape_member_attendance(TEST_MEMBER_ID, TEST_BILL_ID)
        print(f"  ✅ Attendance scraper OK: {len(records)} records")
        for r in records[:3]:
            print(f"    → {r['date']} | {r['clock_in']}–{r['clock_out']} | {r['location'][:30]}")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


async def test_database():
    print("\n[5/6] Testing database connection (Supabase)...")
    from app.database import engine, Base, Member
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    try:
        async with engine.begin() as conn:
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
            # Test query
            result = await conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        print("  ✅ Database connected and tables created")
        return True
    except Exception as e:
        print(f"  ❌ Database failed: {e}")
        print("  Check DATABASE_URL in .env — get it from Supabase → Settings → Database")
        return False


def test_full_discovery():
    print("\n[6/6] Full member discovery (a-z + 0-9)...")
    print("  This takes ~7 seconds — 36 API calls at 150ms each")
    from app.yoactiv.api import discover_all_members
    try:
        members = discover_all_members()
        print(f"  ✅ Discovery complete: {len(members)} unique members")
        print(f"  Sample: {members[0]}")
        if len(members) < 300:
            print(f"  ⚠️  Expected ~398 members, got {len(members)} — some may be missing")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


async def main():
    print("=" * 60)
    print("  AI Gym Assistant — Phase 1 Test Suite")
    print("=" * 60)

    results = []
    results.append(test_cookies())
    if not results[0]:
        print("\n⛔ Cookies invalid — fix cookies.json before running other tests")
        return

    results.append(test_get_client_details())
    results.append(test_getfullsrc())
    results.append(test_attendance_scraper())
    results.append(await test_database())
    results.append(test_full_discovery())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"  Results: {passed}/{total} tests passed")
    if passed == total:
        print("  ✅ ALL TESTS PASSED — Phase 1 complete! Ready for Phase 2.")
    else:
        print("  ⚠️  Some tests failed — fix issues above before proceeding.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
