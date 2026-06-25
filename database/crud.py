from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ANPREvent, Camera


# ─── Camera CRUD ──────────────────────────────────────────────────────────────

async def create_camera(
    db: AsyncSession,
    name: str,
    rtsp_url: str,
    location: Optional[str] = None,
) -> Camera:
    camera = Camera(name=name, rtsp_url=rtsp_url, location=location)
    db.add(camera)
    await db.flush()
    await db.refresh(camera)
    return camera


async def get_camera_by_name(db: AsyncSession, name: str) -> Optional[Camera]:
    result = await db.execute(select(Camera).where(Camera.name == name))
    return result.scalar_one_or_none()


async def list_cameras(db: AsyncSession) -> List[Camera]:
    result = await db.execute(select(Camera).order_by(Camera.name))
    return list(result.scalars().all())


# ─── ANPR Event CRUD ──────────────────────────────────────────────────────────

async def create_event(
    db: AsyncSession,
    plate_number: str,
    timestamp: datetime,
    camera_name: str,
    confidence: float,
    ocr_confidence: float,
    image_path: Optional[str] = None,
    raw_plate_text: Optional[str] = None,
    camera_id: Optional[int] = None,
) -> ANPREvent:
    event = ANPREvent(
        plate_number=plate_number,
        timestamp=timestamp,
        camera_name=camera_name,
        confidence=confidence,
        ocr_confidence=ocr_confidence,
        image_path=image_path,
        raw_plate_text=raw_plate_text,
        camera_id=camera_id,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def get_latest_events(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    camera_name: Optional[str] = None,
) -> tuple[List[ANPREvent], int]:
    query = select(ANPREvent)
    count_query = select(func.count()).select_from(ANPREvent)

    if camera_name:
        query = query.where(ANPREvent.camera_name == camera_name)
        count_query = count_query.where(ANPREvent.camera_name == camera_name)

    query = query.order_by(ANPREvent.timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    count_result = await db.execute(count_query)
    events = list(result.scalars().all())
    total = count_result.scalar_one()
    return events, total


async def search_events(
    db: AsyncSession,
    plate_number: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    camera_name: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[ANPREvent], int]:
    query = select(ANPREvent)
    count_query = select(func.count()).select_from(ANPREvent)

    filters = []
    if plate_number:
        filters.append(ANPREvent.plate_number.ilike(f"%{plate_number}%"))
    if date_from:
        filters.append(ANPREvent.timestamp >= date_from)
    if date_to:
        filters.append(ANPREvent.timestamp <= date_to)
    if camera_name:
        filters.append(ANPREvent.camera_name == camera_name)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    query = query.order_by(ANPREvent.timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    count_result = await db.execute(count_query)
    return list(result.scalars().all()), count_result.scalar_one()


async def count_today_events(db: AsyncSession, camera_name: Optional[str] = None) -> int:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    query = select(func.count()).select_from(ANPREvent).where(
        ANPREvent.timestamp >= today_start
    )
    if camera_name:
        query = query.where(ANPREvent.camera_name == camera_name)
    result = await db.execute(query)
    return result.scalar_one()


async def get_daily_counts(
    db: AsyncSession,
    days: int = 7,
    camera_name: Optional[str] = None,
) -> List[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sql = text(
        """
        SELECT DATE(timestamp AT TIME ZONE 'UTC') AS day,
               COUNT(*) AS total
        FROM anpr_events
        WHERE timestamp >= :since
          AND (:camera IS NULL OR camera_name = :camera)
        GROUP BY day
        ORDER BY day
        """
    )
    result = await db.execute(sql, {"since": since, "camera": camera_name})
    return [{"date": str(row.day), "count": row.total} for row in result.fetchall()]


async def get_hourly_counts(
    db: AsyncSession,
    date: Optional[datetime] = None,
    camera_name: Optional[str] = None,
) -> List[dict]:
    if date is None:
        date = datetime.now(timezone.utc)
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    sql = text(
        """
        SELECT EXTRACT(HOUR FROM timestamp AT TIME ZONE 'UTC')::INT AS hour,
               COUNT(*) AS total
        FROM anpr_events
        WHERE timestamp >= :day_start AND timestamp < :day_end
          AND (:camera IS NULL OR camera_name = :camera)
        GROUP BY hour
        ORDER BY hour
        """
    )
    result = await db.execute(sql, {"day_start": day_start, "day_end": day_end, "camera": camera_name})
    return [{"hour": row.hour, "count": row.total} for row in result.fetchall()]


async def get_frequent_plates(
    db: AsyncSession,
    limit: int = 10,
    days: int = 7,
    camera_name: Optional[str] = None,
) -> List[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sql = text(
        """
        SELECT plate_number,
               COUNT(*) AS total,
               MIN(timestamp) AS first_seen,
               MAX(timestamp) AS last_seen
        FROM anpr_events
        WHERE timestamp >= :since
          AND (:camera IS NULL OR camera_name = :camera)
        GROUP BY plate_number
        ORDER BY total DESC
        LIMIT :limit
        """
    )
    result = await db.execute(sql, {"since": since, "camera": camera_name, "limit": limit})
    return [
        {
            "plate_number": row.plate_number,
            "count": row.total,
            "first_seen": row.first_seen.isoformat() if row.first_seen else None,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        }
        for row in result.fetchall()
    ]


async def get_entry_exit(
    db: AsyncSession,
    plate_number: str,
) -> dict:
    sql = text(
        """
        SELECT MIN(timestamp) AS first_seen,
               MAX(timestamp) AS last_seen,
               COUNT(*) AS total_visits
        FROM anpr_events
        WHERE plate_number = :plate
        """
    )
    result = await db.execute(sql, {"plate": plate_number})
    row = result.fetchone()
    duration = None
    if row and row.first_seen and row.last_seen:
        delta = row.last_seen - row.first_seen
        duration = int(delta.total_seconds())
    return {
        "plate_number": plate_number,
        "first_seen": row.first_seen.isoformat() if row and row.first_seen else None,
        "last_seen": row.last_seen.isoformat() if row and row.last_seen else None,
        "total_visits": row.total_visits if row else 0,
        "duration_seconds": duration,
    }
