

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProfileRecord(Base):
    __tablename__ = "profiles"

    entity_id: Mapped[str] = mapped_column(primary_key=True)
    lat: Mapped[float | None] = mapped_column(nullable=True)
    lon: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    sources: Mapped[list] = mapped_column(type_=JSON)
    identifiers: Mapped[dict] = mapped_column(type_=JSON)
    attributes: Mapped[dict] = mapped_column(type_=JSON)
    raw_ids: Mapped[list] = mapped_column(type_=JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
