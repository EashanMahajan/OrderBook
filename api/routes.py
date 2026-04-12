from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.post("/orders", tags=["orders"])
async def submit_order():
    """Submit a new limit or market order."""
    return {"message": "Order submission — not yet implemented"}


@router.delete("/orders/{order_id}", tags=["orders"])
async def cancel_order(order_id: str):
    """Cancel an existing order by ID."""
    return {"message": f"Cancel order {order_id} — not yet implemented"}


@router.get("/orderbook", tags=["orderbook"])
async def get_orderbook():
    """Return a snapshot of the current order book depth."""
    return {"message": "Order book snapshot — not yet implemented"}


@router.get("/trades", tags=["trades"])
async def get_trades():
    """Return recent trade history."""
    return {"message": "Trade history — not yet implemented"}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time order book and trade streaming.
    Clients connect here to receive live updates.
    """
    await websocket.accept()
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connected — live updates not yet implemented",
        })
        # Keep connection alive until client disconnects
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"echo": data})
    except WebSocketDisconnect:
        pass
