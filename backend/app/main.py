"""
FastAPI application entry point.
Phase 1: Data layer + admin sync endpoints.
Phase 2: JWT auth + member routes added.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, Base, get_db, SyncLog
from app.scheduler import setup_scheduler
from app.yoactiv.cookie_manager import get_cookies_age_warning
from app.yoactiv.sync_engine import (
    run_member_discovery, run_daily_member_status,
    run_billing_sync, run_irregular_sync, run_monthly_register_sync
)

# Phase 2 routes
from app.routes.auth import router as auth_router
from app.routes.member import router as member_router
from app.routes.chat import router as chat_router

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── App lifecycle ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on startup and shutdown."""
    logger.info("=== AI Gym Assistant starting up ===")

    # Create all database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    # Check cookie status on startup
    age_warning = get_cookies_age_warning()
    if age_warning:
        logger.warning(age_warning)

    # Start scheduler
    setup_scheduler()
    logger.info("=== Startup complete ===")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("=== Shutdown complete ===")


# ── FastAPI app ───────────────────────────────────────────────
app = FastAPI(
    title="AI Gym Assistant",
    description="Multi-agent AI system for Muscletech Fitness, Bandlaguda Jagir",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(member_router)
app.include_router(chat_router)


# ── Health checks ─────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check endpoint — used by Railway/Render keep-alive."""
    return {
        "status": "healthy",
        "env": settings.APP_ENV,
        "version": "2.0.0",
    }


@app.get("/health/cookies")
async def cookie_health():
    """Check if Yoactiv cookies are valid right now."""
    from app.yoactiv.cookie_manager import load_cookies, validate_cookies, CookieExpiredError
    try:
        cookies = load_cookies()
        is_valid = validate_cookies(cookies)
        age_warning = get_cookies_age_warning()
        return {
            "cookies_loaded": True,
            "cookies_valid": is_valid,
            "age_warning": age_warning,
            "message": "OK" if is_valid else "Session expired — please update cookies",
        }
    except CookieExpiredError as e:
        return {
            "cookies_loaded": False,
            "cookies_valid": False,
            "age_warning": None,
            "message": str(e),
        }


# ── Admin sync endpoints ───────────────────────────────────────

@app.post("/admin/sync/members")
async def sync_members():
    import asyncio
    asyncio.create_task(run_member_discovery())
    return {"message": "Member discovery started", "status": "running"}


@app.post("/admin/sync/status")
async def sync_status():
    import asyncio
    asyncio.create_task(run_daily_member_status())
    return {"message": "Member status sync started", "status": "running"}


@app.post("/admin/sync/billing")
async def sync_billing():
    import asyncio
    asyncio.create_task(run_billing_sync())
    return {"message": "Billing sync started", "status": "running"}


@app.post("/admin/sync/irregular")
async def sync_irregular():
    import asyncio
    asyncio.create_task(run_irregular_sync())
    return {"message": "Irregular sync started", "status": "running"}


@app.post("/admin/sync/monthly")
async def sync_monthly(year: int = None, month: int = None):
    import asyncio
    asyncio.create_task(run_monthly_register_sync(year, month))
    return {"message": "Monthly register sync started", "status": "running"}


@app.post("/admin/sync/all")
async def sync_all():
    import asyncio

    async def _run_all():
        await run_member_discovery()
        await run_daily_member_status()
        await run_billing_sync()
        await run_irregular_sync()

    asyncio.create_task(_run_all())
    return {"message": "Full sync started", "status": "running"}


@app.get("/admin/sync/logs")
async def get_sync_logs(db: AsyncSession = Depends(get_db), limit: int = 20):
    from sqlalchemy import select, desc
    result = await db.execute(
        select(SyncLog).order_by(desc(SyncLog.started_at)).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "sync_type": log.sync_type,
            "status": log.status,
            "records_processed": log.records_processed,
            "records_updated": log.records_updated,
            "error_message": log.error_message,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        }
        for log in logs
    ]


@app.get("/admin/members/count")
async def member_count(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, func
    from app.database import Member
    result = await db.execute(select(func.count(Member.id)))
    total = result.scalar()
    active = await db.execute(
        select(func.count(Member.id)).where(Member.status == "Active")
    )
    return {"total": total, "active": active.scalar()}
