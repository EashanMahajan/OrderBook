"""
TrainingSession — manages a DQN training run against the live engine.

Runs as an asyncio.Task (NOT a thread) so there is no cross-thread access
to the matching engine.  Simulation agents also run as asyncio tasks on the
same event loop, so all engine mutations are serialised by the event loop —
no locks needed.

The training loop yields to the event loop every YIELD_EVERY steps via
`await asyncio.sleep(0)`.  Each step is fast (~µs), so yielding every 20
steps adds negligible latency while keeping WebSocket heartbeats and
simulation-agent ticks responsive.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from engine.matching_engine import MatchingEngine
from rl.agent import DQNAgent
from rl.env import TradingEnv

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = Path("rl/checkpoints")
CHECKPOINT_FILE = CHECKPOINT_DIR / "latest.pt"

_TRAIN_EVERY = 4   # gradient step every N env steps
_SAVE_EVERY = 10   # checkpoint every N episodes


class TrainingSession:
    """Orchestrates DQN episodes as a single asyncio.Task."""

    def __init__(
        self,
        engine: MatchingEngine,
        target_price: float = 100.0,
        max_steps_per_episode: int = 500,
    ) -> None:
        self.env = TradingEnv(engine, target_price=target_price, max_steps=max_steps_per_episode)
        self.agent = DQNAgent()

        # Training statistics — written only from the event loop, so no locks needed
        self.episode: int = 0
        self.total_steps: int = 0
        self.last_episode_reward: float = 0.0
        self.best_reward: float = float("-inf")
        self.last_loss: float = 0.0
        self.running: bool = False

        self._task: Optional[asyncio.Task] = None

        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        if CHECKPOINT_FILE.exists():
            try:
                self.agent.load(str(CHECKPOINT_FILE))
                logger.info("Loaded RL checkpoint from %s", CHECKPOINT_FILE)
            except Exception as exc:
                logger.warning("Could not load checkpoint: %s", exc)

    # ------------------------------------------------------------------
    # Async control API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop(), name="rl-training")
        logger.info("RL training task started")

    async def stop(self) -> None:
        if not self.running:
            return
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.running = False
        logger.info("RL training stopped after %d episodes", self.episode)

    def status(self) -> dict:
        return {
            "running": self.running,
            "episode": self.episode,
            "total_steps": self.total_steps,
            "last_episode_reward": round(self.last_episode_reward, 4),
            "best_reward": round(self.best_reward, 4) if self.episode > 0 else None,
            "last_loss": round(self.last_loss, 6),
            "epsilon": round(self.agent.eps, 4),
            "buffer_size": len(self.agent.buffer),
        }

    # ------------------------------------------------------------------
    # Training loop (async task — same event loop as simulation agents)
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while True:
            ep_reward = await self._episode()
            self.episode += 1
            self.last_episode_reward = ep_reward
            if ep_reward > self.best_reward:
                self.best_reward = ep_reward
            if self.episode % _SAVE_EVERY == 0:
                self._save_checkpoint()

    async def _episode(self) -> float:
        obs = self.env.reset()
        ep_reward = 0.0
        step_in_ep = 0

        while True:
            action = self.agent.select_action(obs)
            next_obs, reward, done, _ = self.env.step(action)
            self.agent.store(obs, action, reward, next_obs, done)

            ep_reward += reward
            self.total_steps += 1
            step_in_ep += 1

            if step_in_ep % _TRAIN_EVERY == 0:
                loss = self.agent.train_step()
                if loss is not None:
                    self.last_loss = loss
                # Yield after every gradient step — train_step() is the most
                # expensive call (~1-3 ms on CPU). Yielding here ensures
                # simulation agents (25 ms tick interval) are never starved.
                await asyncio.sleep(0)

            obs = next_obs
            if done:
                break

        return ep_reward

    def _save_checkpoint(self) -> None:
        try:
            self.agent.save(str(CHECKPOINT_FILE))
            logger.info(
                "Checkpoint saved | ep=%d reward=%.2f eps=%.3f",
                self.episode, self.last_episode_reward, self.agent.eps,
            )
        except Exception as exc:
            logger.warning("Checkpoint save failed: %s", exc)
