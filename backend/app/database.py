"""
Database models and async session.
All tables designed around confirmed Yoactiv data fields.
"""
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime,
    Text, ForeignKey, UniqueConstraint, Index, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings


# ── Engine & session ──────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.APP_ENV == "development"),
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


class Base(DeclarativeBase):
    pass


# ═══════════════════════════════════════════════════════════════
# MEMBERS
# Source: getfullsrc (name, phone) + getClientDetails (status etc.)
# ═══════════════════════════════════════════════════════════════
class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Yoactiv identity
    yoactiv_member_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)   # also WhatsApp number

    # From getClientDetails
    status: Mapped[Optional[str]] = mapped_column(String(30))        # Active / Inactive / Expired
    service_plan: Mapped[Optional[str]] = mapped_column(String(200)) # e.g. STRENGHT AND CARDIO
    membership_expiry: Mapped[Optional[date]] = mapped_column(Date)
    last_invoiced: Mapped[Optional[date]] = mapped_column(Date)
    total_bills: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin: Mapped[Optional[date]] = mapped_column(Date)
    total_checkins: Mapped[int] = mapped_column(Integer, default=0)

    # Yoactiv billing ID (needed for memsvsess scrape)
    yoactiv_bill_id: Mapped[Optional[str]] = mapped_column(String(20))

    # Dropout & engagement
    is_irregular: Mapped[bool] = mapped_column(Boolean, default=False)  # Yoactiv's own flag
    dropout_score: Mapped[float] = mapped_column(Float, default=0.0)    # 0.0–1.0, our AI score

    # Chatbot login
    chatbot_username: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    chatbot_password_hash: Mapped[Optional[str]] = mapped_column(String(200))

    # Sync metadata
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(back_populates="member", lazy="select")
    billing_records: Mapped[list["BillingRecord"]] = relationship(back_populates="member", lazy="select")
    alerts: Mapped[list["AlertLog"]] = relationship(back_populates="member", lazy="select")
    chat_history: Mapped[list["ChatMessage"]] = relationship(back_populates="member", lazy="select")


# ═══════════════════════════════════════════════════════════════
# ATTENDANCE LOGS
# Source: memsvsess.aspx (individual per member)
# ═══════════════════════════════════════════════════════════════
class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    yoactiv_member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.yoactiv_member_id"), nullable=False, index=True)

    # Date and time
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    clock_in_time: Mapped[Optional[str]] = mapped_column(String(10))   # e.g. "07:32 PM"
    clock_out_time: Mapped[Optional[str]] = mapped_column(String(10))  # e.g. "10:00 PM"

    # Context
    service_name: Mapped[Optional[str]] = mapped_column(String(200))
    location: Mapped[Optional[str]] = mapped_column(String(200))
    pt_no_show: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    source: Mapped[str] = mapped_column(String(30), default="memsvsess")  # or "monthly_register"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Prevent duplicate records
    __table_args__ = (
        UniqueConstraint("yoactiv_member_id", "checkin_date", "clock_in_time", name="uq_attendance"),
        Index("ix_attendance_member_date", "yoactiv_member_id", "checkin_date"),
    )

    member: Mapped["Member"] = relationship(back_populates="attendance_logs")


# ═══════════════════════════════════════════════════════════════
# MONTHLY ATTENDANCE (P/O grid from memviewatt)
# Stores the bulk attendance register — complements AttendanceLog
# ═══════════════════════════════════════════════════════════════
class MonthlyAttendance(Base):
    __tablename__ = "monthly_attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    yoactiv_member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.yoactiv_member_id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Each day 1-30 stored as a character: P=present, 0=absent, -=not in membership period
    # Stored as a 30-char string e.g. "PP0P00PPPPP0------------------"
    days_pattern: Mapped[str] = mapped_column(String(32))
    total_visits: Mapped[int] = mapped_column(Integer, default=0)
    service: Mapped[Optional[str]] = mapped_column(String(200))
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("yoactiv_member_id", "year", "month", name="uq_monthly"),
    )


# ═══════════════════════════════════════════════════════════════
# BILLING RECORDS
# Source: membillpend.aspx
# ═══════════════════════════════════════════════════════════════
class BillingRecord(Base):
    __tablename__ = "billing_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    yoactiv_member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.yoactiv_member_id"), nullable=False, index=True)
    yoactiv_bill_no: Mapped[str] = mapped_column(String(30), unique=True)   # e.g. "Apr83-2026"

    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    service_name: Mapped[Optional[str]] = mapped_column(String(200))
    amount: Mapped[Optional[float]] = mapped_column(Float)
    tax_amount: Mapped[Optional[float]] = mapped_column(Float)
    final_amount: Mapped[Optional[float]] = mapped_column(Float)
    amount_paid: Mapped[Optional[float]] = mapped_column(Float)
    amount_pending: Mapped[Optional[float]] = mapped_column(Float)
    pay_mode: Mapped[Optional[str]] = mapped_column(String(50))  # Credit Card, QR Scanner, Cash
    sale_type: Mapped[Optional[str]] = mapped_column(String(50)) # New Sales, Renewal

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    member: Mapped["Member"] = relationship(back_populates="billing_records")


# ═══════════════════════════════════════════════════════════════
# STAFF USERS (owner dashboard logins)
# ═══════════════════════════════════════════════════════════════
class StaffUser(Base):
    __tablename__ = "staff_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="staff")  # owner / manager / staff
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# ALERT LOG (WhatsApp messages sent)
# ═══════════════════════════════════════════════════════════════
class AlertLog(Base):
    __tablename__ = "alerts_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    yoactiv_member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.yoactiv_member_id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(15))
    alert_type: Mapped[str] = mapped_column(String(50))   # inactivity_nudge, expiry_7day, expiry_1day, re_engagement
    message_preview: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent / failed / skipped
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    member: Mapped["Member"] = relationship(back_populates="alerts")


# ═══════════════════════════════════════════════════════════════
# CHAT MESSAGES (member chatbot history)
# ═══════════════════════════════════════════════════════════════
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    yoactiv_member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.yoactiv_member_id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20))     # user / assistant
    content: Mapped[str] = mapped_column(Text)
    agent_used: Mapped[Optional[str]] = mapped_column(String(50))   # attendance / membership / diet etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    member: Mapped["Member"] = relationship(back_populates="chat_history")


# ═══════════════════════════════════════════════════════════════
# SYNC LOG (audit trail of every sync run)
# ═══════════════════════════════════════════════════════════════
class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sync_type: Mapped[str] = mapped_column(String(50))  # member_discovery, daily_status, etc.
    status: Mapped[str] = mapped_column(String(20))     # running / completed / failed / cookie_expired
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ═══════════════════════════════════════════════════════════════
# DROPOUT SCORE HISTORY
# ═══════════════════════════════════════════════════════════════
class DropoutScoreHistory(Base):
    __tablename__ = "dropout_score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    yoactiv_member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.yoactiv_member_id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float)
    score_date: Mapped[date] = mapped_column(Date, default=date.today)
    factors: Mapped[Optional[str]] = mapped_column(Text)    # JSON string with scoring factors
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
