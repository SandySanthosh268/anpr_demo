from __future__ import annotations

import asyncio
import json
from typing import Dict, Set

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events to all clients."""

    def __init__(self) -> None:
        self._active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._active)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._active.add(websocket)
        logger.info("WS client connected. Total: {n}", n=self.client_count)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._active.discard(websocket)
        logger.info("WS client disconnected. Total: {n}", n=self.client_count)

    async def broadcast(self, payload: dict) -> None:
        """Broadcast a dict payload to every connected client."""
        if not self._active:
            return
        message = json.dumps(payload)
        dead: Set[WebSocket] = set()

        async with self._lock:
            targets = set(self._active)

        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._active -= dead
            logger.debug("Removed {n} dead WS connections.", n=len(dead))

    async def send_heartbeat(self) -> None:
        await self.broadcast({"type": "heartbeat"})


# Singleton shared across the application
ws_manager = ConnectionManager()
