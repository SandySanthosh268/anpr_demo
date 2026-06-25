"""Integration tests for the FastAPI endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio

from database.crud import create_camera, create_event


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_get_latest_events_empty(client):
    resp = await client.get("/plates/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_get_count(client):
    resp = await client.get("/plates/count")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_register_camera(client):
    payload = {"name": "TestGate", "rtsp_url": "rtsp://192.168.1.1/stream", "location": "Main"}
    resp = await client.post("/camera/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "TestGate"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_camera_duplicate(client):
    payload = {"name": "DupGate", "rtsp_url": "rtsp://192.168.1.2/stream"}
    await client.post("/camera/register", json=payload)
    resp = await client.post("/camera/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_cameras(client):
    resp = await client.get("/camera/list")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_search_by_plate(client, db_session):
    await create_event(
        db=db_session,
        plate_number="TN01AB1234",
        timestamp=datetime.now(timezone.utc),
        camera_name="SearchGate",
        confidence=0.95,
        ocr_confidence=0.92,
    )
    await db_session.commit()

    resp = await client.get("/plates/search", params={"plate_number": "TN01"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("TN01AB1234" in e["plate_number"] for e in data["items"])


@pytest.mark.asyncio
async def test_daily_analytics(client):
    resp = await client.get("/analytics/daily", params={"days": 7})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_hourly_analytics(client):
    resp = await client.get("/analytics/hourly")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_frequent_plates(client):
    resp = await client.get("/analytics/frequent", params={"limit": 5})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_entry_exit(client, db_session):
    plate = "MH12XY9999"
    for _ in range(3):
        await create_event(
            db=db_session,
            plate_number=plate,
            timestamp=datetime.now(timezone.utc),
            camera_name="EntryGate",
            confidence=0.9,
            ocr_confidence=0.88,
        )
    await db_session.commit()

    resp = await client.get(f"/analytics/entry-exit/{plate}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plate_number"] == plate
    assert data["total_visits"] >= 3
