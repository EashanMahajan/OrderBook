from fastapi import WebSocket


class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts messages to all clients."""

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._active.discard(websocket)

    async def broadcast(self, data: dict) -> None:
        """Send JSON to all connected clients. Silently removes dead connections."""
        dead = []
        for ws in list(self._active):  # snapshot so discard() during iteration is safe
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._active.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._active)


# Singleton shared across routes and lifespan
manager = ConnectionManager()
