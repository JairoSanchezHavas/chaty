from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.engine import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    brand_color: Mapped[str] = mapped_column(String(16), default="#1A1A2E")
    brand_accent: Mapped[str] = mapped_column(String(16), default="#E94560")
    greeting: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str] = mapped_column(String(256))
    interest: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(128))
    doctor_name: Mapped[str] = mapped_column(String(256))
    doctor_email: Mapped[str] = mapped_column(String(256))
    specialty: Mapped[str] = mapped_column(String(256))
    institution: Mapped[str] = mapped_column(String(256))
    product_interest: Mapped[str] = mapped_column(Text)
    scheduled_at: Mapped[str] = mapped_column(String(64))  # ISO datetime string
    modality: Mapped[str] = mapped_column(String(64), default="presencial")
    gcal_event_id: Mapped[str] = mapped_column(String(256), default="")
    gcal_html_link: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
