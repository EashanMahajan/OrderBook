import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.rate_limiter import RateLimiter
from api.routes import router
from api.ws_manager import manager
from engine.matching_engine import MatchingEngine
from engine.redis_state import RedisStateManager
from simulation.runner import SimulationConfig, create_simulation


async def _snapshot_loop(engine: MatchingEngine) -> None:
    """
    Broadcast a book snapshot to all WebSocket clients at 10 Hz.

    This is the ONLY coroutine that sends to WebSocket clients. Keeping a
    single sender eliminates concurrent send() calls on the same WebSocket
    object, which caused ECONNRESET errors when the on_trade callback
    scheduled many concurrent broadcast tasks.
    """
    while True:
        await asyncio.sleep(0.1)
        if manager.connection_count > 0:
            await manager.broadcast({"type": "snapshot", "data": engine.snapshot()})


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Order Book Simulator starting up...")

    # Redis is optional — engine functions without it
    redis_state = None
    try:
        redis_state = RedisStateManager()
        redis_state._r.ping()
        print("Redis connected — persistence enabled")
    except Exception:
        print("Redis unavailable — running without persistence")
        redis_state = None

    engine = MatchingEngine(redis_state=redis_state)
    # RateLimiter opens its own Redis connection so it never shares the sync
    # client with RedisStateManager. Connection failure is handled internally.
    limiter = RateLimiter()

    app.state.engine = engine
    app.state.redis = redis_state
    app.state.limiter = limiter
    app.state.simulation = None

    broadcast_task = asyncio.create_task(_snapshot_loop(engine))

    # Optional auto-start — set SIM_AUTO_START=true in the environment.
    # SIM_TARGET_PRICE controls the price anchor (default $100).
    if os.getenv("SIM_AUTO_START", "").lower() == "true":
        target_price = float(os.getenv("SIM_TARGET_PRICE", "100.0"))
        cfg = SimulationConfig(target_price=target_price)
        runner = create_simulation(engine, cfg)
        await runner.start()
        app.state.simulation = runner
        print(f"Simulation auto-started (target_price={target_price})")

    yield

    # Shut down simulation before closing infrastructure
    if app.state.simulation and app.state.simulation.is_running:
        await app.state.simulation.stop()

    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass

    if redis_state:
        redis_state._r.close()
    print("Order Book Simulator shut down.")


app = FastAPI(
    title="Order Book Simulator",
    description="Real-time order matching engine with WebSocket broadcast",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint — verifies the server is alive."""
    return {"status": "ok", "service": "order-book-simulator"}
