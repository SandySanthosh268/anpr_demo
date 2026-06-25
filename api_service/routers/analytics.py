from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query

from api_service.dependencies import DBSession
from api_service.schemas import (
    DailyCountItem,
    EntryExitResponse,
    FrequentPlateItem,
    HourlyCountItem,
)
from database.crud import (
    get_daily_counts,
    get_entry_exit,
    get_frequent_plates,
    get_hourly_counts,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/daily", response_model=List[DailyCountItem])
async def daily_counts(
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90, description="Number of past days"),
    camera_name: Optional[str] = Query(default=None),
):
    """Return per-day vehicle counts for the last N days."""
    rows = await get_daily_counts(db, days=days, camera_name=camera_name)
    return [DailyCountItem(date=r["date"], count=r["count"]) for r in rows]


@router.get("/hourly", response_model=List[HourlyCountItem])
async def hourly_counts(
    db: DBSession,
    date: Optional[datetime] = Query(default=None, description="ISO date (defaults to today)"),
    camera_name: Optional[str] = Query(default=None),
):
    """Return per-hour vehicle counts for a specific day."""
    rows = await get_hourly_counts(db, date=date, camera_name=camera_name)
    return [HourlyCountItem(hour=r["hour"], count=r["count"]) for r in rows]


@router.get("/frequent", response_model=List[FrequentPlateItem])
async def frequent_vehicles(
    db: DBSession,
    limit: int = Query(default=10, ge=1, le=100),
    days: int = Query(default=7, ge=1, le=90),
    camera_name: Optional[str] = Query(default=None),
):
    """Return the most frequently seen plates in the last N days."""
    rows = await get_frequent_plates(db, limit=limit, days=days, camera_name=camera_name)
    return [
        FrequentPlateItem(
            plate_number=r["plate_number"],
            count=r["count"],
            first_seen=r["first_seen"],
            last_seen=r["last_seen"],
        )
        for r in rows
    ]


@router.get("/entry-exit/{plate_number}", response_model=EntryExitResponse)
async def entry_exit(db: DBSession, plate_number: str):
    """Return first-seen, last-seen, total visits, and duration for a plate."""
    data = await get_entry_exit(db, plate_number=plate_number.upper())
    return EntryExitResponse(**data)
