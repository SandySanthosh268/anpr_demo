from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from api_service.dependencies import DBSession
from api_service.schemas import CameraRegisterRequest, CameraResponse
from database.crud import create_camera, get_camera_by_name, list_cameras

router = APIRouter(prefix="/camera", tags=["camera"])


@router.post("/register", response_model=CameraResponse, status_code=201)
async def register_camera(db: DBSession, body: CameraRegisterRequest):
    """Register a new IP camera in the system."""
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
