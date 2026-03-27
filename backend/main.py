"""
Skyline — FastAPI Application Entry Point
Run: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import init_db
from routers.history import router as history_router
from routers.video_stream import router as ws_router
from routers.models import router as models_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables. Shutdown: cleanup if needed."""
    await init_db()
    yield


app = FastAPI(
    title="Skyline Intelligence API",
    description="Real-time aerial video analysis — WebSocket inference backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(models_router, prefix="/api")


@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "skyline-backend", "version": "1.0.0"}
