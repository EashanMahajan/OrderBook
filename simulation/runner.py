from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from engine.matching_engine import MatchingEngine
from simulation.market_agents import BaseAgent, MarketMaker, MomentumTrader, NoiseTrader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 5 — SimulationRunner
# ---------------------------------------------------------------------------

class SimulationRunner:
    """
    Manages the lifecycle of a collection of simulation agents.

    Each agent runs in its own asyncio.Task so they are fully isolated —
    a slow or erroring agent cannot block or crash the others.

    start() / stop() are idempotent-safe:
      - Calling start() when already running raises RuntimeError.
      - Calling stop() when already stopped is a no-op.
    """

    def __init__(self, agents: list[BaseAgent]) -> None:
        if not agents:
            raise ValueError("SimulationRunner requires at least one agent")
        self._agents = agents
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Launch every agent as an independent asyncio.Task."""
        if self.is_running:
            raise RuntimeError("Simulation is already running")
        self._tasks = [
            asyncio.create_task(agent.run(), name=agent.name)
            for agent in self._agents
        ]
        logger.info("Simulation started — %d agents active", len(self._tasks))

    async def stop(self) -> None:
        """Cancel all agent tasks and wait for them to finish cleanly."""
        if not self._tasks:
            return
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("Simulation stopped")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if at least one agent task is still active."""
        return bool(self._tasks) and any(not t.done() for t in self._tasks)

    def status(self) -> dict:
        return {
            "running": self.is_running,
            "agent_count": len(self._agents),
            "agents": [a.status() for a in self._agents],
        }


# ---------------------------------------------------------------------------
# Default agent factory
# ---------------------------------------------------------------------------

@dataclass
class SimulationConfig:
    """
    All knobs for the default simulation mix.

    target_price anchors the simulation — all three agent types use it to
    prevent the mid-price from drifting to zero or infinity over time.
    """
    target_price: float = 100.0

    # Agent counts
    market_makers: int = 1
    noise_traders: int = 2
    momentum_traders: int = 1

    # MarketMaker knobs
    mm_spread: float = 0.004        # full spread as fraction of price
    mm_quote_qty: float = 10.0

    # NoiseTrader knobs
    noise_qty_max: float = 15.0
    noise_price_sigma: float = 0.015
    noise_mean_revert_weight: float = 0.25

    # MomentumTrader knobs
    momentum_cooldown: float = 3.0
    momentum_drift_tolerance: float = 0.03
    momentum_trade_qty: float = 5.0
    momentum_lookback: int = 10


def create_simulation(
    engine: MatchingEngine,
    config: Optional[SimulationConfig] = None,
) -> SimulationRunner:
    """
    Build a SimulationRunner from a SimulationConfig.

    Agent naming uses a counter suffix when multiple instances of the
    same type are requested (e.g. noise-1, noise-2).
    """
    cfg = config or SimulationConfig()
    agents: list[BaseAgent] = []

    for i in range(cfg.market_makers):
        suffix = f"-{i + 1}" if cfg.market_makers > 1 else ""
        agents.append(MarketMaker(
            engine=engine,
            name=f"mm{suffix}",
            target_price=cfg.target_price,
            spread=cfg.mm_spread,
            quote_qty=cfg.mm_quote_qty,
        ))

    for i in range(cfg.noise_traders):
        agents.append(NoiseTrader(
            engine=engine,
            name=f"noise-{i + 1}",
            target_price=cfg.target_price,
            qty_max=cfg.noise_qty_max,
            price_sigma=cfg.noise_price_sigma,
            mean_revert_weight=cfg.noise_mean_revert_weight,
        ))

    for i in range(cfg.momentum_traders):
        suffix = f"-{i + 1}" if cfg.momentum_traders > 1 else ""
        agents.append(MomentumTrader(
            engine=engine,
            name=f"momentum{suffix}",
            target_price=cfg.target_price,
            cooldown=cfg.momentum_cooldown,
            drift_tolerance=cfg.momentum_drift_tolerance,
            trade_qty=cfg.momentum_trade_qty,
            lookback=cfg.momentum_lookback,
        ))

    return SimulationRunner(agents)
