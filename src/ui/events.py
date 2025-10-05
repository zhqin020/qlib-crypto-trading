"""
WebSocket event broadcasting system for real-time UI updates
"""

import asyncio
import json
import logging
from typing import Dict, Set, Any
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Broadcast events to connected WebSocket clients"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.event_history: list = []
        self.max_history = 100

    async def connect(self, websocket: WebSocket):
        """Register new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)

        # Send recent event history to new client
        await websocket.send_json({
            "type": "history",
            "events": self.event_history[-20:]  # Last 20 events
        })

        logger.info(f"New WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all connected clients"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)

        # Broadcast to all clients
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(event)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_mcp_event(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        status: str = "success"
    ):
        """Broadcast MCP tool execution event"""
        await self.broadcast("mcp_tool_execution", {
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
            "status": status
        })

    async def broadcast_data_update(self, update_type: str, data: Dict[str, Any]):
        """Broadcast data update event"""
        await self.broadcast("data_update", {
            "update_type": update_type,
            "data": data
        })

    async def broadcast_model_update(self, model_id: str, status: str, metrics: Dict[str, Any] = None):
        """Broadcast model training/update event"""
        await self.broadcast("model_update", {
            "model_id": model_id,
            "status": status,
            "metrics": metrics or {}
        })

    async def broadcast_backtest_update(self, model_id: str, progress: float, metrics: Dict[str, Any] = None):
        """Broadcast backtest progress event"""
        await self.broadcast("backtest_update", {
            "model_id": model_id,
            "progress": progress,
            "metrics": metrics or {}
        })

    async def broadcast_prediction_update(self, model_id: str, predictions: list):
        """Broadcast new predictions event"""
        await self.broadcast("prediction_update", {
            "model_id": model_id,
            "predictions": predictions[:10]  # Top 10
        })

    async def broadcast_notification(self, level: str, message: str, details: Dict[str, Any] = None):
        """Broadcast notification/alert"""
        await self.broadcast("notification", {
            "level": level,  # info, success, warning, error
            "message": message,
            "details": details or {}
        })


# Global event broadcaster instance
event_broadcaster = EventBroadcaster()


def get_event_broadcaster() -> EventBroadcaster:
    """Get global event broadcaster instance"""
    return event_broadcaster
