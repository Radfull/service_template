import time

import pandas as pd
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from market.service import cruds
from market.service.db.db_helper import get_session
from market.service.schemas.features import Features
from market.service.schemas.predictions import PredictionCreate

model_router = APIRouter(prefix="/v1", tags=["model"])


@model_router.post("/predict")
async def predict(
    x: Features,
    request: Request,
    session: AsyncSession | None = Depends(get_session),
):
    t0 = time.perf_counter()
    payload = x.model_dump()
    frame = pd.DataFrame([payload]).reindex(columns=request.app.state.meta["features"])

    arr = request.app.state.pipeline.predict_proba(frame)[0]
    keys = ["A", "B", "C", "D"]
    probs = {k: float(v) for k, v in zip(keys, arr)}
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    segmentation = keys[arr.argmax()]

    pred = await cruds.create_prediction(
        session=session,
        pred_in=PredictionCreate(
            model_version=request.app.state.version,
            features=payload,
            probs=probs,
            segmentation=segmentation,
            latency_ms=latency_ms,
            response_status=200,
        ),
    )
    return pred