from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator

from api.ws_manager import manager
from engine.order import Order, OrderType, Side
from simulation.runner import SimulationConfig, create_simulation

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
    limiter = request.app.state.limiter

    # Rate limit: 10 orders per second per IP
    # request.client is None when requests arrive through a proxy (e.g. Vite dev server)
    client_ip = request.client.host if request.client else "proxy"
    if not await limiter.is_allowed(client_ip, limit=10):
        raise HTTPException(status_code=429, detail="Too many orders. Rate limit: 10/sec")

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
    limiter = request.app.state.limiter

    client_ip = request.client.host if request.client else "proxy"
    if not await limiter.is_allowed(client_ip, limit=10):
        raise HTTPException(status_code=429, detail="Too many cancels. Rate limit: 10/sec")

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
        await websocket.send_json({"type": "snapshot", "data": engine.snapshot()})

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Step 6 — Simulation control endpoints
# ---------------------------------------------------------------------------

class SimulationStartRequest(BaseModel):
    """
    All fields are optional — omit any to use the default.
    target_price is the main anti-drift anchor shared by all agents.
    """
    target_price: float = Field(default=100.0, gt=0, description="Price anchor for all agents")
    market_makers: int = Field(default=1, ge=0, le=5)
    noise_traders: int = Field(default=2, ge=0, le=10)
    momentum_traders: int = Field(default=1, ge=0, le=5)
    mm_spread: float = Field(default=0.004, gt=0, lt=1.0, description="Full bid-ask spread as fraction of price")
    mm_quote_qty: float = Field(default=10.0, gt=0)
    noise_qty_max: float = Field(default=15.0, gt=0)
    noise_price_sigma: float = Field(default=0.015, gt=0, lt=1.0)
    noise_mean_revert_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    momentum_cooldown: float = Field(default=3.0, gt=0, description="Seconds between momentum trades")
    momentum_drift_tolerance: float = Field(default=0.03, gt=0, lt=1.0, description="Drift fraction from target_price that triggers mean-reversion")
    momentum_trade_qty: float = Field(default=5.0, gt=0)
    momentum_lookback: int = Field(default=10, ge=2, le=100)


@router.post("/simulation/start", tags=["simulation"], status_code=201)
async def start_simulation(body: SimulationStartRequest, request: Request):
    """
    Start the market simulation with a configurable agent mix.

    Returns 409 if the simulation is already running.
    All agent types use target_price as their price anchor to prevent
    long-run drift toward zero or infinity.
    """
    if request.app.state.simulation and request.app.state.simulation.is_running:
        raise HTTPException(status_code=409, detail="Simulation is already running")

    cfg = SimulationConfig(
        target_price=body.target_price,
        market_makers=body.market_makers,
        noise_traders=body.noise_traders,
        momentum_traders=body.momentum_traders,
        mm_spread=body.mm_spread,
        mm_quote_qty=body.mm_quote_qty,
        noise_qty_max=body.noise_qty_max,
        noise_price_sigma=body.noise_price_sigma,
        noise_mean_revert_weight=body.noise_mean_revert_weight,
        momentum_cooldown=body.momentum_cooldown,
        momentum_drift_tolerance=body.momentum_drift_tolerance,
        momentum_trade_qty=body.momentum_trade_qty,
        momentum_lookback=body.momentum_lookback,
    )

    runner = create_simulation(request.app.state.engine, cfg)
    await runner.start()
    request.app.state.simulation = runner

    return runner.status()


@router.post("/simulation/stop", tags=["simulation"])
async def stop_simulation(request: Request):
    """
    Stop the running simulation and tear down all agent tasks.

    Returns 400 if no simulation is currently running.
    """
    runner = request.app.state.simulation
    if not runner or not runner.is_running:
        raise HTTPException(status_code=400, detail="No simulation is currently running")

    await runner.stop()
    request.app.state.simulation = None

    return {"running": False}


@router.get("/simulation/status", tags=["simulation"])
async def simulation_status(request: Request):
    """
    Return the current simulation state and per-agent statistics.

    tick_count reflects how many decision cycles each agent has completed.
    MarketMaker additionally reports its live bid/ask order IDs.
    MomentumTrader reports the remaining cooldown before its next trade.
    """
    runner = request.app.state.simulation
    if not runner:
        return {"running": False, "agent_count": 0, "agents": []}

    return runner.status()
