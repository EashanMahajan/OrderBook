from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator

from api.ws_manager import manager
from engine.order import Order, OrderType, Side

router = APIRouter()

class OrderRequest(BaseModel):
    side: Side
    order_type: OrderType
    quantity: float
    price: Optional[float] = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v

    @field_validator("price")
    @classmethod
    def price_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("price must be positive")
        return v


def _order_dict(order: Order) -> dict:
    return {
        "order_id": order.order_id,
        "side": order.side.value,
        "order_type": order.order_type.value,
        "price": order.price,
        "quantity": order.quantity,
        "remaining": order.remaining,
        "status": order.status.value,
        "timestamp": order.timestamp,
    }


def _trade_dict(trade) -> dict:
    return {
        "trade_id": trade.trade_id,
        "buy_order_id": trade.buy_order_id,
        "sell_order_id": trade.sell_order_id,
        "price": trade.price,
        "quantity": trade.quantity,
        "timestamp": trade.timestamp,
    }

@router.post("/orders", tags=["orders"], status_code=201)
async def submit_order(body: OrderRequest, request: Request):
    """
    Submit a new limit or market order to the matching engine.

    - Limit orders require a price. Any unfilled quantity rests on the book.
    - Market orders take the best available price. Unfilled quantity is cancelled.

    Returns the created order and any trades that executed immediately.
    """
    engine = request.app.state.engine

    try:
        order = Order(
            side=body.side,
            order_type=body.order_type,
            quantity=body.quantity,
            price=body.price,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    trades = engine.submit_order(order)

    return {
        "order": _order_dict(order),
        "trades": [_trade_dict(t) for t in trades],
    }

@router.delete("/orders/{order_id}", tags=["orders"])
async def cancel_order(order_id: str, request: Request):
    """
    Cancel an open or partially-filled order by ID.

    Returns 404 if the order does not exist.
    Returns 400 if the order is already fully filled.
    """
    engine = request.app.state.engine

    try:
        order = engine.cancel_order(order_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"order": _order_dict(order)}

@router.get("/orderbook", tags=["orderbook"])
async def get_orderbook(request: Request):
    """
    Return a snapshot of the current order book.

    Includes bids (descending), asks (ascending), spread, order counts,
    and the most recent trades.
    """
    engine = request.app.state.engine
    return engine.snapshot()

@router.get("/trades", tags=["trades"])
async def get_trades(
    request: Request,
    limit: int = Query(default=20, ge=1, le=500, description="Number of recent trades to return"),
):
    """Return recent trade history. Use ?limit=N to control the result size."""
    engine = request.app.state.engine
    snap = engine.snapshot(recent_trade_count=limit)
    return {
        "trades": snap["recent_trades"],
        "total_trades": snap["total_trades"],
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time order book and trade stream.

    On connect: sends a full book snapshot immediately so the client
    starts with live data rather than a blank screen.

    Ongoing: receives trade events (type=trade) and book snapshots
    (type=snapshot) pushed by the REST handlers and the on_trade callback
    after every order submission or cancellation.
    """
    engine = websocket.app.state.engine

    await manager.connect(websocket)
    try:
        # Step 8 — initial snapshot on connect
        await websocket.send_json({"type": "snapshot", "data": engine.snapshot()})

        # Hold the connection open — broadcasts arrive via manager.broadcast()
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
