"""
Yoactiv HTML scrapers.

All selectors confirmed through live testing against real Yoactiv responses.
Key findings documented inline so future developers understand why each
selector was chosen.
"""
import re
import logging
from datetime import date
from bs4 import BeautifulSoup
from .session import get_session, safe_get

logger = logging.getLogger(__name__)


def scrape_member_attendance(member_id: str, bill_id: str) -> list[dict]:
    """
    Scrape full attendance history for one member.

    URL: memsvsess.aspx?mem=ID&bil=BIL_ID
    Confirmed working: 12 dates, 24 clock-in/out times for test member Pranav.

    Selector strategy:
    - The page has 9 tables total.
    - The attendance data table (Table[6]) is identified by containing rows
      that match the date pattern DD-MM-YYYY.
    - Headers confirmed: S.No | Date | Name | Location | Clock in Time |
                         Clock out Time | PT No Show | Medium/Staff

    Args:
        member_id: Yoactiv member ID e.g. "2587500"
        bill_id:   Yoactiv billing ID e.g. "6230391"

    Returns:
        list of dicts with keys: sno, date, name_phone, location,
                                  clock_in, clock_out, pt_no_show
    """
    session = get_session()
    resp = safe_get(session, f"/memsvsess.aspx?mem={member_id}&bil={bill_id}")
    soup = BeautifulSoup(resp.text, "lxml")

    records = []
    date_pattern = re.compile(r"^\d{2}-\d{2}-\d{4}$")  # exact DD-MM-YYYY match

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        # Identify the attendance table by finding rows where:
        # - exactly 8 columns
        # - col[0] is a digit (S.No)
        # - col[1] is exactly DD-MM-YYYY (date column)
        candidate_rows = []
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if (len(cols) == 8
                    and cols[0].isdigit()
                    and date_pattern.match(cols[1])):
                candidate_rows.append(cols)

        if not candidate_rows:
            continue

        # Found the right table — parse clean individual records
        for cols in candidate_rows:
            name_phone = cols[2]
            name, phone = _split_name_phone(name_phone)
            records.append({
                "sno":        cols[0],
                "date":       cols[1],        # DD-MM-YYYY
                "name_phone": name_phone,
                "name":       name,
                "phone":      phone,
                "location":   cols[3],
                "clock_in":   cols[4],        # e.g. "07:32 PM"
                "clock_out":  cols[5],        # e.g. "10:00 PM"
                "pt_no_show": cols[6].lower() == "yes",
            })
        break  # stop after first matching table

    logger.debug(f"Scraped {len(records)} attendance records for member {member_id}")
    return records


def scrape_monthly_register(year: int, month: int) -> list[dict]:
    """
    Scrape the monthly attendance register — all members, each day P/0/-.

    URL: memviewatt.aspx?typ=1&yr=YYYY&mth=MM
    Confirmed working: 164 member rows for April 2026.

    Selector strategy:
    - The page has 11 tables total.
    - CONFIRMED: the data table is Table[7], identified by having exactly
      35 columns: Member Name | Mobile | Service | Expiry Date | Day1..Day30 | Total
    - We filter by len(hdr) == 35 to find it reliably.
    - P = present, 0 = absent, - = outside membership period

    Args:
        year:  4-digit year e.g. 2026
        month: 1-12

    Returns:
        list of dicts with keys: name, mobile, service, expiry,
                                  days (dict {day_num: 'P'/'0'/'-'}),
                                  total_visits
    """
    session = get_session()
    month_str = f"{month:02d}"
    resp = safe_get(session, f"/memviewatt.aspx?typ=1&yr={year}&mth={month_str}&search=")
    soup = BeautifulSoup(resp.text, "lxml")

    records = []
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Check header row for the 35-column structure
        hdr_row = rows[0]
        hdr_cols = [td.get_text(strip=True) for td in hdr_row.find_all(["th", "td"])]

        # The confirmed data table has exactly 35 columns
        if len(hdr_cols) != 35:
            continue

        # Validate it's the right table by checking header names
        # Header: Member Name | Mobile | Service | Expiry Date | Wed01 | Thu02 | ... | Total
        if not ("Member Name" in hdr_cols[0] or hdr_cols[0].strip() == "Member Name"):
            continue

        # Parse data rows
        for row in rows[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) != 35:
                continue

            name = cols[0].strip()
            if not name:
                continue

            # Columns 4-33 are the daily attendance markers (30 days)
            # Column 34 is total visits
            days = {}
            for i in range(30):
                day_num = i + 1
                marker = cols[4 + i].strip()
                days[day_num] = marker if marker in ("P", "0", "-") else marker

            total_str = cols[34].strip()
            total_visits = int(total_str) if total_str.isdigit() else 0

            records.append({
                "name":         name,
                "mobile":       cols[1].strip(),
                "service":      cols[2].strip(),
                "expiry":       cols[3].strip(),    # DD-MM-YYYY string
                "days":         days,               # {1: 'P', 2: '0', 3: '-', ...}
                "total_visits": total_visits,
            })

        # Found the right table — stop here
        if records:
            logger.info(f"Monthly register {year}-{month_str}: {len(records)} member rows scraped")
            break

    if not records:
        logger.warning(f"No data found in monthly register for {year}-{month_str}")

    return records


def scrape_irregular_members() -> list[str]:
    """
    Scrape Yoactiv's own dropout-tagged (irregular) member list.

    URL: memshiplist.aspx?fbhvtyp=1
    Returns: list of member_id strings

    Note: Yoactiv's "irregular" definition is based on their own internal
    algorithm. We sync this daily and use it alongside our AI dropout score
    as a validation signal.
    """
    session = get_session()
    resp = safe_get(session, "/memshiplist.aspx?fbhvtyp=1")

    # Regex on raw HTML — confirmed to extract mid= references correctly
    mid_refs = re.findall(r"memshiplist\.aspx\?mid=(\d+)", resp.text)
    unique_ids = list(set(mid_refs))

    logger.info(f"Irregular members: {len(unique_ids)} Yoactiv-tagged IDs")
    return unique_ids


def scrape_billing(from_date: str, to_date: str) -> list[dict]:
    """
    Scrape payment records for a date range.

    URL: membillpend.aspx?dlDate=1&frm=DD-MM-YYYY&tod=DD-MM-YYYY
    Confirmed: page loads correctly — 0 rows means no payments in range.

    Args:
        from_date: DD-MM-YYYY string
        to_date:   DD-MM-YYYY string

    Returns:
        list of payment record dicts (may be empty if no payments in range)
    """
    session = get_session()
    url = f"/membillpend.aspx?dlDate=1&frm={from_date}&tod={to_date}"
    resp = safe_get(session, url)
    soup = BeautifulSoup(resp.text, "lxml")

    records = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]

            # Payment data rows start with a numeric S.No
            if not cols or not cols[0].isdigit():
                continue
            if len(cols) < 8:
                continue

            records.append({
                "sno":         cols[0],
                "bill_no":     cols[1] if len(cols) > 1 else "",
                "paid_date":   cols[2] if len(cols) > 2 else "",
                "type":        cols[3] if len(cols) > 3 else "",     # New Sales / Renewal
                "location":    cols[4] if len(cols) > 4 else "",
                "member_id":   cols[5] if len(cols) > 5 else "",
                "member_name": cols[6] if len(cols) > 6 else "",
                "phone":       cols[7] if len(cols) > 7 else "",
                "service":     cols[8] if len(cols) > 8 else "",
                "amount":      _parse_amount(cols[9] if len(cols) > 9 else ""),
                "tax":         _parse_amount(cols[10] if len(cols) > 10 else ""),
                "final":       _parse_amount(cols[11] if len(cols) > 11 else ""),
                "paid":        _parse_amount(cols[12] if len(cols) > 12 else ""),
                "pending":     _parse_amount(cols[13] if len(cols) > 13 else ""),
                "pay_mode":    cols[14] if len(cols) > 14 else "",
            })

    logger.info(f"Billing scrape {from_date}→{to_date}: {len(records)} payment records")
    return records


# ── Internal helpers ──────────────────────────────────────────
def _split_name_phone(name_phone: str) -> tuple[str, str]:
    """
    Split Yoactiv's "Name-Phone" format.
    Example: "Pranav Sai Reddy-7330801909" → ("Pranav Sai Reddy", "7330801909")
    """
    # Find phone number: 10 digits starting with 6-9
    phone_match = re.search(r"([6-9]\d{9})$", name_phone.strip())
    if phone_match:
        phone = phone_match.group(1)
        name = name_phone[:name_phone.rfind(phone)].rstrip("-").strip()
        return name, phone
    return name_phone, ""


def _parse_amount(value: str) -> float | None:
    """Parse rupee amount string to float. Returns None if not parseable."""
    try:
        # Remove rupee symbol, commas, spaces
        cleaned = re.sub(r"[₹,\s]", "", value)
        return float(cleaned) if cleaned else None
    except ValueError:
        return None