# backend/app/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, Member, StaffUser
from .jwt_handler import decode_token

bearer = HTTPBearer()

# ─── Member auth ──────────────────────────────────────────────

async def get_current_member(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Member:
    """
    Validates the Bearer JWT and returns the Member object.
    Used on all member-facing routes (/chat, /member/me, etc.)
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(creds.credentials)
        if payload.get("role") != "member":
            raise exc
        member_id: str = payload.get("sub")
        if not member_id:
            raise exc
    except JWTError:
        raise exc

    result = await db.execute(
        select(Member).where(Member.yoactiv_member_id == member_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise exc
    return member


# ─── Staff auth ───────────────────────────────────────────────

async def get_current_staff(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> StaffUser:
    """
    Validates the Bearer JWT and returns the StaffUser object.
    Accepts roles: owner, manager, staff.
    Used on all dashboard routes (/admin/*)
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(creds.credentials)
        if payload.get("role") not in ("owner", "manager", "staff"):
            raise exc
        staff_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise exc

    result = await db.execute(
        select(StaffUser).where(StaffUser.id == staff_id)
    )
    staff = result.scalar_one_or_none()
    if not staff or not staff.is_active:
        raise exc
    return staff


async def require_owner(
    staff: StaffUser = Depends(get_current_staff),
) -> StaffUser:
    """
    Extra guard: staff role must be 'owner'.
    Used on revenue and sensitive admin routes.
    """
    if staff.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return staff
