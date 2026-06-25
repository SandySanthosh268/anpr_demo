from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from api_service.ws_manager import ws_manager
from config import get_settings

settings = get_settings()
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/anpr")
async def anpr_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time ANPR event streaming.

    Clients receive:
    - { "type": "heartbeat" }  — every WS_HEARTBEAT_INTERVAL seconds
    - { "plate": "...", "timestamp": "...", "confidence": float, "camera": "..." }
    """
    await ws_manager.connect(websocket)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            # Keep connection alive; actual events are pushed via broadcast()
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WS client disconnected cleanly.")
    except Exception as exc:
        logger.warning("WS error: {err}", err=exc)
    finally:
        heartbeat_task.cancel()
        await ws_manager.disconnect(websocket)


async def _heartbeat(websocket: WebSocket) -> None:
    """Sends a heartbeat ping so idle connections don't time out."""
    try:
        while True:
            await asyncio.sleep(settings.ws_heartbeat_interval)
            await websocket.send_json({"type": "heartbeat"})
    except Exception:
        pass
