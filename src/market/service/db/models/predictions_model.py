from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from typing import Any

from .base_db_model import BaseDbModel

class Predictions(BaseDbModel):
    __tablename__ = "predictions"

    time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    model_version: Mapped[str]
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)
    probs: Mapped[dict[str, float]] = mapped_column(JSONB)
    segmentation: Mapped[str]
    latency_ms: Mapped[float]
    response_status: Mapped[int]

