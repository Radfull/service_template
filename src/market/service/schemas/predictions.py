import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class PredictionBase(BaseModel):
    request_id: uuid.UUID
    model_version: str
    features: dict[str,Any]
    probs: dict[str,float]
    segmentation: str
    latency_ms: float
    response_status: int

class PredictionCreate(PredictionBase):
    pass

class PredictionUpdate(PredictionCreate):
    pass

class PredictionUpdatePartial(PredictionCreate):
    model_version: str | None
    features: dict[str,Any] | None
    probs: dict[str,float] | None
    latency_ms: float | None
    response_status: int | None


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: uuid.UUID
    model_version: str
    probs: dict[str, float]
    segmentation: str
    latency_ms: float
    response_status: int

class Prediction(PredictionBase):
    model_config = ConfigDict(from_attributes=True)