from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from api_service.routers import analytics, camera, plates, websocket
from api_service.schemas import HealthResponse
from api_service.ws_manager import ws_manager
from config import get_settings
from database.base import Base
from database.session import engine
from pipeline.anpr_pipeline import ANPRPipeline

settings = get_settings()
_pipeline: ANPRPipeline | None = None
_pipeline_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _pipeline, _pipeline_task

    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting ANPR System (env={env})", env=settings.app_env)

    # Create tables if they don't exist (Alembic handles production migrations)
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured.")

    # Ensure snapshot directory exists
    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Start ANPR pipeline as a background task
    _pipeline = ANPRPipeline(broadcast_callback=ws_manager.broadcast)
    _pipeline_task = asyncio.create_task(_pipeline.run(), name="anpr_pipeline")
    logger.info("ANPR Pipeline task started.")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down ANPR System…")
    if _pipeline:
        _pipeline.stop()
    if _pipeline_task and not _pipeline_task.done():
        _pipeline_task.cancel()
        try:
            await _pipeline_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Production-ready Real-Time ANPR System for Indian number plates.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(plates.router)
    app.include_router(analytics.router)
    app.include_router(camera.router)
    app.include_router(websocket.router)

    # ── Static snapshots ──────────────────────────────────────────────────────
    app.mount("/snapshots", StaticFiles(directory=str(settings.snapshot_dir)), name="snapshots")

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check() -> HealthResponse:
        global _pipeline, _pipeline_task
        pipeline_running = _pipeline_task is not None and not _pipeline_task.done()
        camera_connected = _pipeline.camera_stats.is_connected if _pipeline else False
        return HealthResponse(
            status="ok",
            version="1.0.0",
            pipeline_running=pipeline_running,
            camera_connected=camera_connected,
            ws_clients=ws_manager.client_count,
        )

    return app


app = create_app()
