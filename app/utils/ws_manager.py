"""
WebSocket Manager utility — handles real-time logs streaming for active audit runs.
"""

from fastapi import WebSocket
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages active WebSocket connections grouped by audit_run_id."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        """Accept connection and add it to the run_id group."""
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)
        logger.info("WebSocket connected for run: %s. Total connections: %d", run_id, len(self.active_connections[run_id]))

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        """Remove connection from the run_id group."""
        if run_id in self.active_connections:
            try:
                self.active_connections[run_id].remove(websocket)
                if not self.active_connections[run_id]:
                    del self.active_connections[run_id]
                logger.info("WebSocket disconnected for run: %s", run_id)
            except ValueError:
                pass

    async def broadcast(self, run_id: str, message: dict) -> None:
        """Send a JSON payload to all WebSockets in the run_id group."""
        if run_id in self.active_connections:
            conns = list(self.active_connections[run_id])
            for ws in conns:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.debug("Failed to send WS message: %s. Disconnecting.", str(e))
                    self.disconnect(run_id, ws)


# Global WebSocket manager instance
ws_manager = WebSocketManager()
