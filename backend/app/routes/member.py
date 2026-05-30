# backend/app/routes/member.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, Member, AttendanceLog
from app.auth.dependencies import get_current_member

router = APIRouter(prefix="/member", tags=["member"])


@router.get("/me")
async def get_my_profile(current_member: Member = Depends(get_current_member)):
    """
    Returns the logged-in member's profile.
    Phone number is intentionally excluded (PII).
    """
    return {
        "name": current_member.name,
        "status": current_member.status,
        "service_plan": current_member.service_plan,
        "membership_expiry": str(current_member.membership_expiry) if current_member.membership_expiry else None,
        "total_checkins": current_member.total_checkins,
        "last_checkin": str(current_member.last_checkin) if current_member.last_checkin else None,
        "dropout_score": current_member.dropout_score,
    }


@router.get("/attendance")
async def get_my_attendance(
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
):
    """
    Returns recent attendance logs for the logged-in member.
    Default: last 30 check-ins. Max: 100.
    """
    limit = min(limit, 100)  # cap at 100 to prevent heavy queries

    result = await db.execute(
        select(AttendanceLog)
        .where(AttendanceLog.yoactiv_member_id == current_member.yoactiv_member_id)
        .order_by(AttendanceLog.checkin_date.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "date": str(log.checkin_date),
            "clock_in": str(log.clock_in_time) if log.clock_in_time else None,
            "clock_out": str(log.clock_out_time) if log.clock_out_time else None,
            "location": log.location,
        }
        for log in logs
    ]
