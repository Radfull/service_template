import logging
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from market.config import settings
from market.model_store import load_model
from market.service import cruds
from market.service.api.v1.model import model_router
from market.service.db.db_helper import db_helper
from market.service.db.models.base_db_model import BaseDbModel
from market.service.schemas.predictions import PredictionCreate

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info('Starting app')

    app.state.pipeline, app.state.meta, app.state.version = load_model()
    logger.info(
        "Loaded model source=%s name=%s alias=%s version=%s",
        app.state.meta.get("model_source"),
        app.state.meta.get("model_name"),
        app.state.meta.get("model_alias"),
        app.state.version,
    )

    if db_helper is not None:
        async with db_helper.engine.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(123456789)"))
            await conn.run_sync(BaseDbModel.metadata.create_all)
    
    yield

    app.state.pipeline = None
    if db_helper is not None:
        await db_helper.dispose()
    logging.info("Stopping app")

app = FastAPI(title="Market ML Service",
              version = settings.service_version,
              lifespan=lifespan)

# routers
app.include_router(model_router)

# 422
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    request_id = uuid.uuid4()
    body = exc.body if isinstance(exc.body, dict) else {}

    logger.warning(
        "validation failed request_id=%s errors=%s", request_id, exc.errors()
    )

    if db_helper is not None:
        try:
            async with db_helper.session_factory() as session:
                await cruds.create_prediction(
                    session=session,
                    pred_in=PredictionCreate(
                        request_id=request_id,
                        model_version=getattr(request.app.state, "version", "unknown"),
                        features=body,
                        probs={},
                        segmentation="INVALID",
                        latency_ms=0.0,
                        response_status=422,
                    ),
                )
        except Exception:
            logger.exception("failed to persist 422 for request_id=%s", request_id)

    return JSONResponse(
        status_code=422,
        content={"request_id": str(request_id), "detail": exc.errors()},
    )


# 500
@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    request_id = uuid.uuid4()
    logger.exception("unhandled error request_id=%s", request_id)

    if db_helper is not None:
        try:
            async with db_helper.session_factory() as session:
                await cruds.create_prediction(
                    session=session,
                    pred_in=PredictionCreate(
                        request_id=request_id,
                        model_version=getattr(request.app.state, "version", "unknown"),
                        features={},
                        probs={},
                        segmentation="ERROR",
                        latency_ms=0.0,
                        response_status=500,
                    ),
                )
        except Exception:
            logger.exception("failed to persist 500 for request_id=%s", request_id)

    return JSONResponse(
        status_code=500,
        content={"request_id": str(request_id), "detail": "internal error"},
    )


@app.get("/health")
def check_health():
    return {"status" : "ok",
            "service_version" : settings.service_version,
            "db_allow": db_helper is not None,
            "model_path": settings.model_path,
            "log_level": settings.log_level,
            "model_version" : app.state.version,
            "model_source": app.state.meta.get("model_source"),
            "model_name": app.state.meta.get("model_name"),
            "model_alias": app.state.meta.get("model_alias"),
            "model_run_id": app.state.meta.get("run_id")}

@app.get("/ready")
def check_ready():
    if getattr(app.state, "pipeline", None) is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {"status": "ready", "db_allow": db_helper is not None}

def main():
    uvicorn.run("main:app")

if __name__ == "__main__":
    main()
