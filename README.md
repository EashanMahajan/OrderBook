# Order Book Simulator

A real-time exchange order book simulator with a price-time priority matching engine, WebSocket streaming, and a live visualization dashboard.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│   Frontend   │◄────│  WebSocket   │◄────│  Matching  │
│  React/D3.js │     │   Server     │     │   Engine   │
└─────────────┘     └──────────────┘     └─────┬─────┘
                                               │
                    ┌──────────────┐            │
                    │   REST API   │◄───────────┤
                    │   FastAPI    │            │
                    └──────────────┘      ┌────▼─────┐
                                          │   Redis   │
                    ┌──────────────┐      │  State    │
                    │  Simulation  │─────►│  Store    │
                    │   Agents     │      └──────────┘
                    └──────────────┘
```

## Features

- **Order Matching Engine** — Price-time priority matching for limit and market orders with partial fill support
- **Redis State Management** — Persistent order book state with sorted sets, order hashes, and trade logs
- **WebSocket Streaming** — Real-time broadcast of book updates and trade executions to all connected clients
- **Market Simulation** — Configurable synthetic agents (market maker, momentum, noise) that generate realistic order flow
- **Live Dashboard** — D3.js depth chart, trade tape, and mid-price chart updating in real time
- **REST API** — Submit orders, cancel, query book state, and view trade history

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn api.main:app --reload --port 8000

# Run tests
pytest -v
```

## Project Structure

```
order-book-simulator/
├── engine/
│   ├── order.py             # Order & Trade dataclasses
│   ├── orderbook.py         # Bid/ask book with heap-based price levels
│   └── matching_engine.py   # Price-time priority matching logic
├── api/
│   ├── main.py              # FastAPI app entry point
│   └── routes.py            # REST + WebSocket endpoints
├── simulation/
│   └── market_agents.py     # Synthetic market participants
├── frontend/                # React + D3.js dashboard (Phase 7)
├── tests/                   # pytest test suite
├── requirements.txt
├── pytest.ini
└── README.md
```

## Tech Stack

| Layer | Tool |
|-------|------|
| Core Engine | Python |
| Real-time Comms | WebSockets (FastAPI) |
| Order State | Redis |
| Backend API | FastAPI |
| Frontend | React + D3.js |
| Testing | pytest + Locust |
| Deployment | Docker + AWS EC2 |
