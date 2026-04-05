# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class EventEnvelope(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    kind: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    alt_m: Optional[float] = None
    entity_id: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_coords(self) -> EventEnvelope:
        if self.lat is not None and not (-90 <= self.lat <= 90):
            raise ValueError(f"lat out of range: {self.lat}")
        if self.lon is not None and not (-180 <= self.lon <= 180):
            raise ValueError(f"lon out of range: {self.lon}")
        return self

    def to_redis(self) -> dict[str, str]:
        """Serialise for Redis XADD -- all values must be strings."""
        return {"data": self.model_dump_json()}

    @classmethod
    def from_redis(cls, fields: dict[str, str]) -> EventEnvelope:
        return cls.model_validate_json(fields["data"])
