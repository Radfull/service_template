import uvicorn
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import logging
import joblib

from market.config import settings
from market.service.db.db_helper import db_helper
from market.service.db.models.base_db_model import BaseDbModel
from market.service.api.v1.model import model_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info('Starting app')

    bundle = joblib.load(settings.model_path)
    app.state.pipeline = bundle["pipeline"]
    app.state.meta = bundle["metadata"]
    app.state.version = bundle["metadata"]["model_version"]

    if db_helper is not None:
        async with db_helper.engine.begin() as conn:
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


@app.get("/health")
def check_health():
    return {"status" : "ok", "service_version" : settings.service_version, "db_allow": db_helper is not None}

@app.get("/ready")
def check_ready():
    if getattr(app.state, "pipeline", "None") is  None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {"status": "ready", "db_allow": db_helper is not None}

def main():
    uvicorn.run("main:app")

if __name__ == "__main__":
    main()