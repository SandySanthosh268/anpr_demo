from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api_service.dependencies import DBSession
from api_service.schemas import (
    ANPREventResponse,
    EventCountResponse,
    PaginatedEventsResponse,
)
from database.crud import (
    count_today_events,
    get_latest_events,
    search_events,
)

router = APIRouter(prefix="/plates", tags=["plates"])


@router.get("/latest", response_model=PaginatedEventsResponse)
async def get_latest(
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    camera_name: Optional[str] = Query(default=None),
):
    """Return the most recent ANPR events, newest first."""
    offset = (page - 1) * page_size
    events, total = await get_latest_events(
        db, limit=page_size, offset=offset, camera_name=camera_name
    )
    return PaginatedEventsResponse(
        items=[ANPREventResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/search", response_model=PaginatedEventsResponse)
async def search_plates(
    db: DBSession,
    plate_number: Optional[str] = Query(default=None, description="Partial plate match"),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    camera_name: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """Search events by plate number, date range, or camera."""
    offset = (page - 1) * page_size
    events, total = await search_events(
        db,
        plate_number=plate_number,
        date_from=date_from,
        date_to=date_to,
        camera_name=camera_name,
        limit=page_size,
        offset=offset,
    )
    return PaginatedEventsResponse(
        items=[ANPREventResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/count", response_model=EventCountResponse)
async def get_count(
    db: DBSession,
    camera_name: Optional[str] = Query(default=None),
):
    """Return today's vehicle count."""
    from datetime import date

    total = await count_today_events(db, camera_name=camera_name)
    return EventCountResponse(
        total=total,
        camera_name=camera_name,
        date=str(date.today()),
    )
