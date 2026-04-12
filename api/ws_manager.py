from fastapi import WebSocket


class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts messages to all clients."""

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active:
            self._active.remove(websocket)

    async def broadcast(self, data: dict) -> None:
        """Send JSON to all connected clients. Silently removes dead connections."""
        dead = []
        for ws in self._active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._active.remove(ws)

    @property
    def connection_count(self) -> int:
        return len(self._active)


# Singleton shared across routes and lifespan
manager = ConnectionManager()
