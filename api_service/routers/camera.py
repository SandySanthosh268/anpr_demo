from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from api_service.dependencies import DBSession
from api_service.schemas import CameraRegisterRequest, CameraResponse
from api_service.source_manager import source_manager
from database.crud import create_camera, get_camera_by_name, list_cameras

router = APIRouter(prefix="/camera", tags=["camera"])

VIDEOS_DIR = Path("videos")
VIDEOS_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".ts", ".flv", ".webm"}


@router.post("/register", response_model=CameraResponse, status_code=201)
async def register_camera(db: DBSession, body: CameraRegisterRequest):
    """Register a new video source (RTSP stream or local file path)."""
    existing = await get_camera_by_name(db, body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Camera '{body.name}' already registered.")

    camera = await create_camera(
        db, name=body.name, rtsp_url=body.rtsp_url, location=body.location
    )
    await db.commit()
    return CameraResponse.model_validate(camera)


@router.get("/list", response_model=List[CameraResponse])
async def list_all_cameras(db: DBSession):
    """List all registered cameras."""
    cameras = await list_cameras(db)
    return [CameraResponse.model_validate(c) for c in cameras]


@router.post("/upload-video", status_code=201)
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file and return its server path for use as a camera source."""
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest = VIDEOS_DIR / unique_name

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "filename": file.filename,
        "path": str(dest),
        "url": f"/videos/{unique_name}",
    }


@router.post("/set-active")
async def set_active_source(db: DBSession, name: str):
    """Switch the live pipeline to this camera source immediately."""
    camera = await get_camera_by_name(db, name)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{name}' not found.")
    if not camera.is_active:
        raise HTTPException(status_code=400, detail=f"Camera '{name}' is disabled.")

    source_manager.change(url=camera.rtsp_url, name=camera.name)
    return {"status": "switching", "camera": name, "url": camera.rtsp_url}


@router.post("/switch")
async def switch_source(url: str, name: str):
    """Directly switch the pipeline to any URL or file path (no DB registration required)."""
    if not url.strip():
        raise HTTPException(status_code=422, detail="url must not be empty.")
    if not name.strip():
        raise HTTPException(status_code=422, detail="name must not be empty.")
    source_manager.change(url=url.strip(), name=name.strip())
    return {"status": "switching", "name": name, "url": url}


@router.get("/active-source")
async def get_active_source():
    """Return the currently active pipeline source."""
    return {"name": source_manager.name, "url": source_manager.url}
