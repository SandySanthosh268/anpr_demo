from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api_service.source_manager import source_manager

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/status")
async def pipeline_status():
    return {
        "is_file_source": source_manager.is_file_source,
        "pipeline_active": source_manager.pipeline_active,
        "name": source_manager.name,
        "url": source_manager.url,
    }


@router.post("/play")
async def play_pipeline():
    if not source_manager.is_file_source:
        raise HTTPException(
            status_code=400,
            detail="Play/Stop is only for local video files. RTSP streams run continuously.",
        )
    source_manager.play()
    return {"status": "playing", "name": source_manager.name}


@router.post("/stop")
async def stop_pipeline():
    if not source_manager.is_file_source:
        raise HTTPException(
            status_code=400,
            detail="Play/Stop is only for local video files. RTSP streams run continuously.",
        )
    source_manager.stop()
    return {"status": "stopped", "name": source_manager.name}
