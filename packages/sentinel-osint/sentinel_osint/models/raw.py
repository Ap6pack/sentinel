

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RawRecord(Base):
    __tablename__ = "raw_records"

    id: Mapped[str] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String, index=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    lat: Mapped[float | None] = mapped_column(nullable=True)
    lon: Mapped[float | None] = mapped_column(nullable=True)
    raw_data: Mapped[dict] = mapped_column(type_=JSON)
    collected_at: Mapped[datetime] = mapped_column(server_default=func.now())
