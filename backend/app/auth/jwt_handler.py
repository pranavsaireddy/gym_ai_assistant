# backend/app/auth/jwt_handler.py
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.config import settings


def create_access_token(data: dict) -> str:
    """Create a signed JWT. data must include 'sub' and 'role'."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises JWTError if invalid or expired."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def create_member_token(yoactiv_member_id: str) -> str:
    """Create a token for a gym member."""
    return create_access_token({"sub": yoactiv_member_id, "role": "member"})


def create_staff_token(staff_id: int, role: str) -> str:
    """Create a token for a staff user (owner / manager / staff)."""
    return create_access_token({"sub": str(staff_id), "role": role})
