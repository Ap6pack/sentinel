

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    confidence: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(String)
    reasoning: Mapped[str] = mapped_column(String)
    recommended_action: Mapped[str] = mapped_column(String)
    linked_entity_ids: Mapped[list] = mapped_column(type_=JSON)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_ids: Mapped[list] = mapped_column(type_=JSON)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
