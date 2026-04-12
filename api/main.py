from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan — runs on startup and shutdown.
    Redis and matching engine initialization will go here in Phase 4–5.
    """
    print("🚀 Order Book Simulator starting up...")
    yield
    print("🛑 Order Book Simulator shutting down...")


app = FastAPI(
    title="Order Book Simulator",
    description="Real-time order matching engine with WebSocket broadcast",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend to connect during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(router)


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint — verifies the server is alive."""
    return {"status": "ok", "service": "order-book-simulator"}
