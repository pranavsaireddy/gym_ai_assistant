"""
Yoactiv Sync Engine
All sync jobs call ensure_valid_session() first (via session_manager).
Cookies are loaded from Supabase; Playwright/auto-login is not used.
"""
import logging
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import (
    AsyncSessionLocal, Member, AttendanceLog, MonthlyAttendance,
    BillingRecord, SyncLog
)
from app.yoactiv.cookie_manager import CookieExpiredError, get_cookies_age_warning
from app.yoactiv.api import discover_all_members, get_client_details, get_member_bill_id
from app.yoactiv.scraper import (
    scrape_member_attendance, scrape_monthly_register,
    scrape_irregular_members, scrape_billing
)

logger = logging.getLogger(__name__)


async def _ensure_session():
    """
    Loads cookies from Supabase via session_manager before any sync job.
    """
    from app.yoactiv.session_manager import ensure_valid_session
    await ensure_valid_session()


# ═══════════════════════════════════════════════════════════════
# JOB 1: Member Discovery
# ═══════════════════════════════════════════════════════════════
async def run_member_discovery():
    """
    Discover all member IDs via getfullsrc a-z+0-9.
    Upserts new members into DB. Does NOT overwrite existing data.
    Confirmed: finds 398 members in ~7 seconds.
    """
    log = await _start_sync_log("member_discovery")
    logger.info("=== Starting member discovery ===")

    try:
        await _ensure_session()    # ← AUTO-LOGIN if needed
        members = discover_all_members()

        async with AsyncSessionLocal() as db:
            new_count = 0
            for m in members:
                existing = await db.execute(
                    select(Member).where(Member.yoactiv_member_id == m["member_id"])
                )
                existing_member = existing.scalar_one_or_none()

                if existing_member is None:
                    db.add(Member(
                        yoactiv_member_id=m["member_id"],
                        name=m["name"],
                        phone=m["phone"],
                    ))
                    new_count += 1
                else:
                    if m["name"] and m["name"] != existing_member.name:
                        existing_member.name = m["name"]
                    if m["phone"] and not existing_member.phone:
                        existing_member.phone = m["phone"]

            await db.commit()

        await _complete_sync_log(log, "completed", records_processed=len(members), records_updated=new_count)
        logger.info(f"Member discovery done: {len(members)} total, {new_count} new")

    except CookieExpiredError as e:
        await _complete_sync_log(log, "cookie_expired", error=str(e))
        _alert_cookie_expired(str(e))
    except Exception as e:
        await _complete_sync_log(log, "failed", error=str(e))
        logger.error(f"Member discovery failed: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════
# JOB 2: Daily Member Status
# ═══════════════════════════════════════════════════════════════
async def run_daily_member_status():
    """
    Update status, expiry, last_checkin, total_checkins for every member.
    Calls getClientDetails per member. ~398 API calls at 0.3s = ~2 min.
    """
    log = await _start_sync_log("daily_member_status")
    logger.info("=== Starting daily member status sync ===")

    try:
        await _ensure_session()    # ← AUTO-LOGIN if needed

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Member.yoactiv_member_id))
            all_ids = [row[0] for row in result.fetchall()]

        logger.info(f"Syncing status for {len(all_ids)} members...")
        updated = 0
        cookie_error = None

        for mid in all_ids:
            try:
                details = get_client_details(mid)

                async with AsyncSessionLocal() as db:
                    member = await db.execute(
                        select(Member).where(Member.yoactiv_member_id == mid)
                    )
                    member = member.scalar_one_or_none()
                    if member:
                        member.status = details["status"] or member.status
                        member.last_invoiced = _parse_date(details["last_invoiced"])
                        member.total_bills = details["total_bills"] or member.total_bills
                        member.last_checkin = _parse_date(details["last_checkin"])
                        member.total_checkins = details["total_checkins"] or member.total_checkins
                        member.last_synced = datetime.utcnow()
                        await db.commit()
                        updated += 1

            except CookieExpiredError as e:
                cookie_error = str(e)
                break
            except Exception as e:
                logger.warning(f"Status sync failed for member {mid}: {e}")
                continue

        if cookie_error:
            await _complete_sync_log(log, "cookie_expired", records_processed=updated, error=cookie_error)
            _alert_cookie_expired(cookie_error)
        else:
            await _complete_sync_log(log, "completed", records_processed=len(all_ids), records_updated=updated)
            logger.info(f"Daily status sync done: {updated}/{len(all_ids)} updated")

    except Exception as e:
        await _complete_sync_log(log, "failed", error=str(e))
        logger.error(f"Daily status sync failed: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════
# JOB 3: Attendance Sync (per member)
# ═══════════════════════════════════════════════════════════════
async def run_attendance_sync_for_member(member_id: str, bill_id: str | None = None):
    """Sync attendance history for one specific member."""
    try:
        await _ensure_session()    # ← AUTO-LOGIN if needed

        if not bill_id:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Member.yoactiv_bill_id).where(Member.yoactiv_member_id == member_id)
                )
                bill_id = result.scalar_one_or_none()

            if not bill_id:
                logger.info(f"Fetching bill_id for member {member_id}...")
                bill_id = get_member_bill_id(member_id)
                if bill_id:
                    async with AsyncSessionLocal() as db:
                        await db.execute(
                            update(Member)
                            .where(Member.yoactiv_member_id == member_id)
                            .values(yoactiv_bill_id=bill_id)
                        )
                        await db.commit()

        if not bill_id:
            logger.warning(f"Cannot sync attendance for {member_id} — no bill_id found")
            return

        records = scrape_member_attendance(member_id, bill_id)

        async with AsyncSessionLocal() as db:
            new_records = 0
            for r in records:
                existing = await db.execute(
                    select(AttendanceLog).where(
                        AttendanceLog.yoactiv_member_id == member_id,
                        AttendanceLog.checkin_date == _parse_date(r["date"]),
                        AttendanceLog.clock_in_time == r["clock_in"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                db.add(AttendanceLog(
                    yoactiv_member_id=member_id,
                    checkin_date=_parse_date(r["date"]),
                    clock_in_time=r["clock_in"],
                    clock_out_time=r["clock_out"],
                    location=r["location"],
                    pt_no_show=r["pt_no_show"],
                    source="memsvsess",
                ))
                new_records += 1

            await db.commit()

        logger.debug(f"Attendance sync {member_id}: {len(records)} records, {new_records} new")

    except CookieExpiredError:
        raise
    except Exception as e:
        logger.warning(f"Attendance sync failed for {member_id}: {e}")


# ═══════════════════════════════════════════════════════════════
# JOB 4: Monthly Register
# ═══════════════════════════════════════════════════════════════
async def run_monthly_register_sync(year: int = None, month: int = None):
    """Sync the full monthly P/O attendance grid for all members."""
    today = date.today()
    year = year or today.year
    month = month or today.month

    log = await _start_sync_log("monthly_register")
    logger.info(f"=== Starting monthly register sync {year}-{month:02d} ===")

    try:
        await _ensure_session()    # ← AUTO-LOGIN if needed
        records = scrape_monthly_register(year, month)

        async with AsyncSessionLocal() as db:
            synced = 0
            for r in records:
                member_result = await db.execute(
                    select(Member).where(Member.phone == r["mobile"])
                )
                member = member_result.scalar_one_or_none()
                if not member:
                    continue

                existing = await db.execute(
                    select(MonthlyAttendance).where(
                        MonthlyAttendance.yoactiv_member_id == member.yoactiv_member_id,
                        MonthlyAttendance.year == year,
                        MonthlyAttendance.month == month,
                    )
                )
                existing_record = existing.scalar_one_or_none()
                days_str = "".join(r["days"].get(i, "-") for i in range(1, 31))

                if existing_record:
                    existing_record.days_pattern = days_str
                    existing_record.total_visits = r["total_visits"]
                    existing_record.synced_at = datetime.utcnow()
                else:
                    db.add(MonthlyAttendance(
                        yoactiv_member_id=member.yoactiv_member_id,
                        year=year, month=month,
                        days_pattern=days_str,
                        total_visits=r["total_visits"],
                        service=r["service"],
                        expiry_date=_parse_date(r["expiry"]),
                    ))
                synced += 1

            await db.commit()

        await _complete_sync_log(log, "completed", records_processed=len(records), records_updated=synced)
        logger.info(f"Monthly register done: {synced}/{len(records)} rows synced")

    except CookieExpiredError as e:
        await _complete_sync_log(log, "cookie_expired", error=str(e))
        _alert_cookie_expired(str(e))
    except Exception as e:
        await _complete_sync_log(log, "failed", error=str(e))
        logger.error(f"Monthly register sync failed: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════
# JOB 5: Billing Sync
# ═══════════════════════════════════════════════════════════════
async def run_billing_sync():
    """Sync payment records from last 3 days."""
    today = date.today()
    from_date = (today - timedelta(days=3)).strftime("%d-%m-%Y")
    to_date = today.strftime("%d-%m-%Y")

    log = await _start_sync_log("billing_sync")
    logger.info(f"=== Starting billing sync {from_date}→{to_date} ===")

    try:
        await _ensure_session()    # ← AUTO-LOGIN if needed
        records = scrape_billing(from_date, to_date)

        async with AsyncSessionLocal() as db:
            new_count = 0
            for r in records:
                if not r.get("bill_no") or not r.get("member_id"):
                    continue
                existing = await db.execute(
                    select(BillingRecord).where(BillingRecord.yoactiv_bill_no == r["bill_no"])
                )
                if existing.scalar_one_or_none():
                    continue

                db.add(BillingRecord(
                    yoactiv_member_id=r["member_id"],
                    yoactiv_bill_no=r["bill_no"],
                    paid_date=_parse_date(r["paid_date"]),
                    service_name=r["service"],
                    amount=r["amount"],
                    final_amount=r["final"],
                    amount_paid=r["paid"],
                    amount_pending=r["pending"],
                    pay_mode=r["pay_mode"],
                    sale_type=r["type"],
                ))
                new_count += 1

            await db.commit()

        await _complete_sync_log(log, "completed", records_processed=len(records), records_updated=new_count)
        logger.info(f"Billing sync done: {new_count} new records")

    except CookieExpiredError as e:
        await _complete_sync_log(log, "cookie_expired", error=str(e))
        _alert_cookie_expired(str(e))
    except Exception as e:
        await _complete_sync_log(log, "failed", error=str(e))
        logger.error(f"Billing sync failed: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════
# JOB 6: Irregular Members
# ═══════════════════════════════════════════════════════════════
async def run_irregular_sync():
    """Sync Yoactiv's own dropout-tagged member list."""
    log = await _start_sync_log("irregular_sync")

    try:
        await _ensure_session()    # ← AUTO-LOGIN if needed
        irregular_ids = scrape_irregular_members()

        async with AsyncSessionLocal() as db:
            await db.execute(update(Member).values(is_irregular=False))
            if irregular_ids:
                await db.execute(
                    update(Member)
                    .where(Member.yoactiv_member_id.in_(irregular_ids))
                    .values(is_irregular=True)
                )
            await db.commit()

        await _complete_sync_log(log, "completed", records_updated=len(irregular_ids))
        logger.info(f"Irregular sync done: {len(irregular_ids)} members flagged")

    except CookieExpiredError as e:
        await _complete_sync_log(log, "cookie_expired", error=str(e))
        _alert_cookie_expired(str(e))
    except Exception as e:
        await _complete_sync_log(log, "failed", error=str(e))
        logger.error(f"Irregular sync failed: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════
def _alert_cookie_expired(message: str):
    """Log a prominent alert. Playwright should have prevented this."""
    border = "=" * 65
    logger.error(border)
    logger.error("COOKIE ERROR — Playwright auto-login may have failed")
    logger.error(message)
    logger.error("Check that YOACTIV_USERNAME and YOACTIV_PASSWORD are set in .env")
    logger.error("Or paste cookies manually into app/yoactiv/cookies.json as fallback")
    logger.error(border)


async def _start_sync_log(sync_type: str) -> SyncLog:
    async with AsyncSessionLocal() as db:
        log = SyncLog(sync_type=sync_type, status="running")
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log


async def _complete_sync_log(
    log: SyncLog, status: str,
    records_processed: int = 0, records_updated: int = 0,
    error: str = None
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SyncLog).where(SyncLog.id == log.id))
        log_record = result.scalar_one_or_none()
        if log_record:
            log_record.status = status
            log_record.records_processed = records_processed
            log_record.records_updated = records_updated
            log_record.error_message = error
            log_record.completed_at = datetime.utcnow()
            await db.commit()


def _parse_date(date_str: str | None) -> date | None:
    if not date_str or date_str.strip() in ("", "-", "N/A"):
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%Y").date()
    except ValueError:
        return None
