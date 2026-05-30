"""
Test Playwright Auto-Login — with diagnostics
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

async def main():
    print("=" * 55)
    print("  Playwright Auto-Login Test")
    print("=" * 55)

    print("\n[1/3] Checking environment variables...")
    username = os.environ.get("YOACTIV_USERNAME", "")
    password = os.environ.get("YOACTIV_PASSWORD", "")
    if not username:
        print("  ❌ YOACTIV_USERNAME not set in .env"); return
    if not password:
        print("  ❌ YOACTIV_PASSWORD not set in .env"); return
    print(f"  ✅ YOACTIV_USERNAME = {username}")
    print(f"  ✅ YOACTIV_PASSWORD = {'*' * len(password)}")

    print("\n[2/3] Running Playwright auto-login (~8 seconds)...")
    print("      (opening headless browser, navigating to Yoactiv...)")
    try:
        from app.yoactiv.playwright_login import auto_login
        cookies = await auto_login()
        print(f"  ✅ Login successful!")
        print(f"     ASP.NET_SessionId: {cookies['ASP.NET_SessionId'][:14]}...")
        print(f"     AWSALB:            {cookies['AWSALB'][:14]}...")
        print(f"     AWSALBCORS:        {cookies['AWSALBCORS'][:14]}...")
    except ImportError:
        print("  ❌ Playwright not installed!")
        print("  → Run: pip install playwright && playwright install chromium"); return
    except Exception as e:
        print(f"  ❌ Login failed: {e}")
        print("\n  Running visible browser diagnostic...")
        await _diagnose(username, password); return

    print("\n[3/3] Verifying cookies saved to cookies.json...")
    try:
        from app.yoactiv.cookie_manager import get_valid_cookies
        get_valid_cookies()
        print("  ✅ cookies.json updated and validated!")
    except Exception as e:
        print(f"  ❌ Validation failed: {e}"); return

    print("\n" + "=" * 55)
    print("  ✅ ALL TESTS PASSED — auto-login working!")
    print("=" * 55)


async def _diagnose(username, password):
    """Opens a visible browser to show exactly what Playwright sees."""
    from playwright.async_api import async_playwright
    print("\n  Opening VISIBLE browser (don't touch it — closes in 12 sec)...")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
        try:
            print("  → Navigating to backstage.yoactiv.com ...")
            await page.goto("https://backstage.yoactiv.com",
                            wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2000)
            print(f"  → Current URL:  {page.url}")
            print(f"  → Page title:   {await page.title()}")
            inputs = await page.query_selector_all("input")
            print(f"  → Input fields found: {len(inputs)}")
            for inp in inputs:
                n = await inp.get_attribute("name") or "-"
                t = await inp.get_attribute("type") or "-"
                i = await inp.get_attribute("id") or "-"
                print(f"     type={t:<10} name={n:<25} id={i}")
            await page.wait_for_timeout(10000)
        except Exception as e:
            print(f"  → Diagnostic error: {e}")
        finally:
            await browser.close()
    print("\n  Paste the output above and we will fix the selectors.")

if __name__ == "__main__":
    asyncio.run(main())