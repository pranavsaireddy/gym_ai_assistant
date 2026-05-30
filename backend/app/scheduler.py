"""
APScheduler — all jobs. All times IST (Asia/Kolkata).
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR

from app.yoactiv.sync_engine import (
    run_member_discovery, run_daily_member_status,
    run_billing_sync, run_irregular_sync, run_monthly_register_sync,
)
from app.yoactiv.session_manager import run_keepalive

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def _on_job_error(event):
    logger.error(f"Scheduler job error: {event.job_id} — {event.exception}")


def setup_scheduler() -> AsyncIOScheduler:
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    # Keepalive — every 15 min, keeps ASP.NET_SessionId alive
    # This is why the session never expires during gym hours
    scheduler.add_job(
        run_keepalive,
        IntervalTrigger(minutes=15),
        id="keepalive",
        name="Yoactiv session keepalive",
        max_instances=1,
        misfire_grace_time=60,
    )

    # Weekly member discovery — 9PM Sunday (gym PC still on)
    # Moved from 3AM to avoid the overnight gap
    scheduler.add_job(
        run_member_discovery,
        CronTrigger(day_of_week="sun", hour=21),
        id="member_discovery",
        name="Weekly member discovery",
        max_instances=1,
        misfire_grace_time=600,
    )

    # Daily member status — 6AM (gym PC on by then, cookie agent pushed at 5AM)
    scheduler.add_job(
        run_daily_member_status,
        CronTrigger(hour=6),
        id="daily_member_status",
        name="Daily member status sync",
        max_instances=1,
        misfire_grace_time=1800,
    )

    # Billing — 7AM
    scheduler.add_job(
        run_billing_sync,
        CronTrigger(hour=7),
        id="billing_sync",
        name="Daily billing sync",
        max_instances=1,
        misfire_grace_time=600,
    )

    # Irregular — 7:30AM
    scheduler.add_job(
        run_irregular_sync,
        CronTrigger(hour=7, minute=30),
        id="irregular_sync",
        name="Daily irregular sync",
        max_instances=1,
        misfire_grace_time=600,
    )

    # Monthly register — 9PM on 1st of month (gym PC still on)
    # Moved from 2AM to avoid the overnight gap
    scheduler.add_job(
        run_monthly_register_sync,
        CronTrigger(day=1, hour=21),
        id="monthly_register",
        name="Monthly register sync",
        max_instances=1,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("Scheduler started — keepalive every 15 min + 5 sync jobs (IST)")
    return scheduler
