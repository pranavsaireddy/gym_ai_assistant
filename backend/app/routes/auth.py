# backend/app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from pydantic import BaseModel

from app.database import get_db, Member, StaffUser
from app.auth.jwt_handler import create_member_token, create_staff_token

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Request models ───────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


# ─── Member login ─────────────────────────────────────────────

@router.post("/member/login")
async def member_login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Member logs in with their generated chatbot_username + password.
    Returns JWT token + member name for the chat UI to display.
    """
    result = await db.execute(
        select(Member).where(Member.chatbot_username == body.username)
    )
    member = result.scalar_one_or_none()

    if not member or not member.chatbot_password_hash:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not pwd_ctx.verify(body.password, member.chatbot_password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_member_token(member.yoactiv_member_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "member_name": member.name,
        "member_id": member.yoactiv_member_id,
    }


# ─── Staff login ──────────────────────────────────────────────

@router.post("/staff/login")
async def staff_login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Owner / manager / staff logs in with staff credentials.
    Returns JWT token + role for dashboard role-gating.
    """
    result = await db.execute(
        select(StaffUser).where(StaffUser.username == body.username)
    )
    staff = result.scalar_one_or_none()

    if not staff or not staff.is_active:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not pwd_ctx.verify(body.password, staff.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_staff_token(staff.id, staff.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": staff.role,
        "full_name": staff.full_name,
    }
