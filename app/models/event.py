from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.order import Order


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False, server_default="sport")
    sport_type: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_time: Mapped[time] = mapped_column(Time, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    orders: Mapped[list[Order]] = relationship(back_populates="event")
