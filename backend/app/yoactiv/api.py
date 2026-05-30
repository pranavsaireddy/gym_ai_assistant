"""
Yoactiv JSON API callers.

Endpoints confirmed working through live testing:
  - getfullsrc:       returns member ID + name + phone (HTML encoded)
  - getClientDetails: returns member status summary (double-encoded JSON)

Both require valid browser cookies in cookies.json.
"""
import json
import re
import logging
from bs4 import BeautifulSoup
from .session import get_session, safe_post

logger = logging.getLogger(__name__)


def get_client_details(member_id: str) -> dict:
    """
    Fetch summary data for one member from getClientDetails.

    Confirmed response fields (tested live):
        Status, Last Contacted, Last Invoiced, Total Bills,
        Last Check-in Date, Total Check-ins

    Args:
        member_id: Yoactiv member ID string e.g. "2587500"

    Returns:
        dict with keys: status, last_contacted, last_invoiced,
                        total_bills, last_checkin, total_checkins
    """
    session = get_session()
    data = safe_post(
        session,
        "/autofill.asmx/getClientDetails",
        {"Member_ID": member_id},
        delay=0.3,
    )

    raw = data.get("d", "{}")

    # Response is double-encoded: d is a JSON string containing {"Results": "<html>"}
    try:
        inner = json.loads(raw)
        html_str = inner.get("Results", "")
    except (json.JSONDecodeError, TypeError):
        html_str = raw   # fallback: d is the HTML directly

    # Parse the HTML string into key-value pairs
    soup = BeautifulSoup(html_str, "html.parser")
    text = soup.get_text(separator="\n")

    fields = {}
    for line in text.split("\n"):
        line = line.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()

    return {
        "status":           fields.get("Status", ""),
        "last_contacted":   fields.get("Last Contacted", ""),
        "last_invoiced":    fields.get("Last Invoiced", ""),
        "total_bills":      _safe_int(fields.get("Total Bills", "0")),
        "last_checkin":     fields.get("Last Check-in Date", ""),
        "total_checkins":   _safe_int(fields.get("Total Check-ins", "0")),
    }


def discover_all_members() -> list[dict]:
    """
    Discover ALL member IDs by searching a–z + 0–9 via getfullsrc.

    Strategy confirmed through live testing:
    - 36 API calls total (26 letters + 10 digits)
    - Returns 398 unique members in ~7 seconds
    - Each response: HTML string with <a href='memshiplist.aspx?mid=ID'>Name - Phone</a>

    Returns:
        list of dicts with keys: member_id, name, phone
    """
    session = get_session()
    all_members: dict[str, dict] = {}

    search_chars = list("abcdefghijklmnopqrstuvwxyz") + list("0123456789")
    logger.info(f"Starting member discovery ({len(search_chars)} search characters)...")

    for char in search_chars:
        try:
            data = safe_post(
                session,
                "/autofill.asmx/getfullsrc",
                {"src": char, "typ": "1"},
                delay=0.15,   # 150ms between calls — polite rate limit
            )

            raw_html = data.get("d", "")
            if not raw_html:
                continue

            soup = BeautifulSoup(raw_html, "html.parser")
            links = soup.find_all("a", href=re.compile(r"mid=\d+"))

            for link in links:
                mid_match = re.search(r"mid=(\d+)", link.get("href", ""))
                if not mid_match:
                    continue

                mid = mid_match.group(1)
                if mid in all_members:
                    continue   # already seen from another letter

                name_raw = link.get_text(strip=True)
                parts = name_raw.split(" - ", 1)
                name = parts[0].strip() if parts else name_raw
                phone = parts[1].strip() if len(parts) > 1 else ""

                # Validate phone: Indian mobile numbers start with 6-9, 10 digits
                if phone and not re.match(r"^[6-9]\d{9}$", phone):
                    phone = ""   # not a valid phone — may be extra text

                all_members[mid] = {
                    "member_id": mid,
                    "name":      name,
                    "phone":     phone,
                }

        except Exception as e:
            logger.warning(f"getfullsrc failed for char '{char}': {e}")
            continue

    members_list = list(all_members.values())
    logger.info(f"Member discovery complete: {len(members_list)} unique members found")
    return members_list


def get_member_bill_id(member_id: str) -> str | None:
    """
    Extract the billing ID for a member by scraping their profile page.
    The billing ID is needed to call memsvsess.aspx for attendance history.

    URL: memshiplist.aspx?mid=MEMBER_ID
    Looks for: href containing bil=NUMBER

    Returns billing ID string or None if not found.
    """
    from .session import HTML_HEADERS
    session = get_session()

    try:
        resp = session.get(
            f"/memshiplist.aspx?mid={member_id}",
            headers=HTML_HEADERS,
        )
        import time; time.sleep(0.3)

        bill_matches = re.findall(r"bil=(\d+)", resp.text)
        if bill_matches:
            return bill_matches[0]
        return None
    except Exception as e:
        logger.warning(f"Could not get bill_id for member {member_id}: {e}")
        return None


# ── Internal helpers ──────────────────────────────────────────
def _safe_int(value: str) -> int:
    """Convert string to int safely, returning 0 on failure."""
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return 0
