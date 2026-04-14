# Order Book Simulator

A real-time exchange order book simulator with a price-time priority matching engine, WebSocket streaming, market simulation agents, natural-language order entry powered by Claude, and a reinforcement learning trading agent.

**Live demo → [orderbook-production-f3f2.up.railway.app](https://orderbook-production-f3f2.up.railway.app/)**

---

## Features

- **Price-Time Priority Matching Engine** — Limit and market orders with partial fill support, heap-based price levels
- **WebSocket Streaming** — 10 Hz broadcast of full order book snapshots to all connected clients
- **Market Simulation Agents** — Configurable mix of synthetic agents generating realistic order flow:
  - **MarketMaker** — continuous two-sided quotes with anti-drift target price anchor
  - **NoiseTrader** — random limit orders with mean-reversion weighting
  - **MomentumTrader** — follows recent trade direction, overrides to mean-revert on large price drifts
- **RL Trading Agent (DQN)** — Deep Q-Network that learns to trade against the live book. Trains on-the-fly against the simulated market; checkpoint survives restarts. Deploy the trained agent as a live participant.
- **Natural Language Order Entry** — Describe trades in plain English ("Buy 5 at 1% below mid"); Claude interprets and submits the orders
- **Live Dashboard** — Order book depth chart, mid-price chart, trade feed, and per-agent statistics
- **Redis Persistence** — Optional Redis backend for order book state and rate limiting (falls back to in-memory)
- **REST API** — Full CRUD for orders, simulation control, RL training control, and AI order entry

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  React Frontend (Vite)                │
│  OrderBook │ DepthChart │ PriceChart │ TradeFeed      │
│  SimControl │ RLAgentPanel │ NLOrderEntry │ OrderEntry │
└────────────────────────┬─────────────────────────────┘
                         │  HTTP + WebSocket
┌────────────────────────▼─────────────────────────────┐
│                   FastAPI Backend                      │
│                                                        │
│  /orders  /orderbook  /trades  /simulation/*           │
│  /rl/train/*  /ai/order  /ws                           │
│                                                        │
│  ┌──────────────────┐   ┌──────────────────────────┐  │
│  │  Matching Engine │   │    Simulation Runner      │  │
│  │  (price-time     │◄──│  MarketMaker              │  │
│  │   priority)      │   │  NoiseTrader              │  │
│  └────────┬─────────┘   │  MomentumTrader           │  │
│           │             │  RLAgent (DQN inference)  │  │
│  ┌────────▼─────────┐   └──────────────────────────┘  │
│  │  Redis (optional)│                                  │
│  └──────────────────┘   ┌──────────────────────────┐  │
│                         │   DQN Training Session    │  │
│                         │   (asyncio task, on-line) │  │
│                         └──────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   Claude API         │
              │  (NL order parsing)  │
              └─────────────────────┘
```

---

## Project Structure

```
order_book_simulator/
├── engine/
│   ├── order.py               # Order, Trade dataclasses and enums
│   ├── orderbook.py           # Heap-based bid/ask book, price-time priority
│   ├── matching_engine.py     # Matching logic, snapshot, flush
│   └── redis_state.py         # Optional Redis persistence layer
├── api/
│   ├── main.py                # FastAPI app, lifespan, static file serving
│   ├── routes.py              # All REST + WebSocket endpoints
│   ├── ws_manager.py          # WebSocket connection manager
│   ├── rate_limiter.py        # Sliding-window rate limiter (Redis + in-memory)
│   └── ai.py                  # Claude API integration for NL order parsing
├── simulation/
│   ├── market_agents.py       # MarketMaker, NoiseTrader, MomentumTrader, RLAgent
│   └── runner.py              # SimulationRunner, SimulationConfig factory
├── rl/
│   ├── env.py                 # TradingEnv — gym-style MDP wrapper
│   ├── agent.py               # DQNAgent — Q-network, replay buffer, train step
│   ├── train.py               # TrainingSession — async task, checkpointing
│   └── checkpoints/           # Saved model weights (latest.pt)
├── frontend/                  # React + TypeScript (Vite)
│   └── src/
│       ├── components/        # OrderBook, DepthChart, PriceChart, TradeFeed,
│       │                      # SimControl, RLAgentPanel, NLOrderEntry, OrderEntry
│       ├── hooks/             # useMarketFeed (WebSocket + snapshot diffing)
│       ├── store/             # Zustand market state store
│       └── lib/               # Types
├── tests/                     # pytest suite
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Quick Start (local)

```bash
# 1. Create virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set environment variables (copy and edit)
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# 4. Start the backend
uvicorn api.main:app --reload --port 8000

# 5. Start the frontend dev server (separate terminal)
cd frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies all API and WebSocket calls to the backend.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | For AI orders | — | Claude API key for natural-language order entry |
| `REDIS_URL` | No | — | Redis connection URL (`redis://...`). Falls back to in-memory if unset |
| `SIM_AUTO_START` | No | `false` | Auto-start the market simulation on boot |
| `SIM_TARGET_PRICE` | No | `100.0` | Price anchor for auto-started simulation |

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/orders` | Submit a limit or market order |
| `DELETE` | `/orders/{id}` | Cancel an open order |
| `GET` | `/orderbook` | Current book snapshot |
| `GET` | `/trades` | Recent trade history |
| `POST` | `/simulation/start` | Start the agent simulation |
| `POST` | `/simulation/stop` | Stop the simulation |
| `POST` | `/simulation/reset` | Stop + flush all orders and trades |
| `GET` | `/simulation/status` | Per-agent statistics |
| `POST` | `/rl/train/start` | Start DQN training session |
| `POST` | `/rl/train/stop` | Stop training (checkpoint saved) |
| `GET` | `/rl/status` | Training statistics and epsilon |
| `POST` | `/ai/order` | Parse and submit a natural-language order |
| `GET` | `/ws` | WebSocket — 10 Hz book snapshot stream |
| `GET` | `/health` | Health check |

---

## RL Agent

The DQN agent learns to trade against the live simulated market:

- **State** (15-dim): best bid/ask, spread, top-3 depth quantities, price momentum, agent position, mark-to-market PnL
- **Actions** (6): hold, buy market, sell market, buy limit at bid, sell limit at ask, cancel all
- **Reward**: Δ(mark-to-market) − inventory penalty × |position|
- **Training**: runs as an asyncio task alongside simulation agents; yields every gradient step to avoid starving the market maker

**Workflow:**
1. Start the simulation (provides liquidity for the agent to trade against)
2. Click **Start Training** in the RL Agent panel — watch epsilon decay from 1.0 → 0.05 as the agent shifts from exploration to learned policy
3. Checkpoint saves every 10 episodes to `rl/checkpoints/latest.pt`
4. To deploy: stop the simulation, enable the **RL Agent** toggle in SimControl, restart

---

## Tech Stack

| Layer | Tool |
|---|---|
| Matching Engine | Python — heap-based price-time priority |
| Backend API | FastAPI + uvicorn |
| Real-time | WebSockets — 10 Hz snapshot broadcast |
| State Persistence | Redis (optional) |
| RL | PyTorch — DQN with experience replay |
| AI Order Entry | Anthropic Claude API (tool use + prompt caching) |
| Frontend | React + TypeScript (Vite) |
| State Management | Zustand |
| Testing | pytest + Locust |
| Deployment | Docker + Railway |
