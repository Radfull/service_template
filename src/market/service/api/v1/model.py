import time
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from market.service import cruds
from market.service.db.db_helper import get_session
from market.service.schemas.features import Features
from market.service.schemas.predictions import PredictionCreate, PredictionRead

model_router = APIRouter(prefix="/v1", tags=["model"])


@model_router.post("/predict", response_model=PredictionRead)
async def predict(
    x: Features,
    request: Request,
    session: AsyncSession | None = Depends(get_session),
) -> PredictionRead:
    t0 = time.perf_counter()
    request_id = uuid.uuid4()                                    

    payload = x.model_dump(by_alias=True)
    expected = list(request.app.state.meta["features"])
    frame = pd.DataFrame([payload]).reindex(columns=expected)
    if frame.isna().all(axis=None):
        raise HTTPException(status_code=422, detail="feature names mismatch")

    arr = request.app.state.pipeline.predict_proba(frame)[0]
    keys = ["A", "B", "C", "D"]
    probs = {k: float(v) for k, v in zip(keys, arr)}
    segmentation = keys[arr.argmax()]
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    await cruds.create_prediction(                            
        session=session,
        pred_in=PredictionCreate(
            request_id=request_id,
            model_version=request.app.state.version,
            features=payload,
            probs=probs,
            segmentation=segmentation,
            latency_ms=latency_ms,
            response_status=200,                                     
        ),
    )

    return PredictionRead(                                        
        request_id=request_id,
        model_version=request.app.state.version,
        probs=probs,
        segmentation=segmentation,
        latency_ms=latency_ms,
        response_status=200,
    )