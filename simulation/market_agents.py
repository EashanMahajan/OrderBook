from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from engine.matching_engine import MatchingEngine
from engine.order import Order, OrderStatus, OrderType, Side

logger = logging.getLogger(__name__)

# Lazy imports for RL to avoid hard dependency when not used
_rl_available: bool | None = None

def _check_rl() -> bool:
    global _rl_available
    if _rl_available is None:
        try:
            import torch  # noqa: F401
            _rl_available = True
        except ImportError:
            _rl_available = False
    return _rl_available


# ---------------------------------------------------------------------------
# Step 1 — Base Agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """
    Abstract base for all simulation agents.

    Subclasses implement tick(). The run() coroutine calls tick() every
    tick_interval seconds and is meant to be launched as an asyncio.Task.
    Exceptions in tick() are logged and swallowed so a single bad tick never
    kills the agent loop.

    Provides two safe helpers:
      _submit() — builds and submits an Order, returns (order, trades) or (None, [])
      _cancel() — cancels by ID, returns True/False; False just means it was already
                  filled or not found, both of which are normal in live trading.
    """

    def __init__(
        self,
        engine: MatchingEngine,
        name: str,
        target_price: float,
        tick_interval: float,
    ) -> None:
        self._engine = engine
        self.name = name
        self.target_price = target_price
        self.tick_interval = tick_interval
        self.tick_count: int = 0

    @abstractmethod
    async def tick(self) -> None:
        """Single agent decision cycle. Called every tick_interval seconds."""

    async def run(self) -> None:
        """Main loop — runs until the asyncio Task is cancelled."""
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[%s] tick error: %s", self.name, exc)
            self.tick_count += 1
            await asyncio.sleep(self.tick_interval)

    def status(self) -> dict:
        return {
            "name": self.name,
            "type": type(self).__name__,
            "tick_count": self.tick_count,
            "target_price": self.target_price,
            "tick_interval_ms": self.tick_interval * 1000,
        }

    # ------------------------------------------------------------------
    # Safe helpers
    # ------------------------------------------------------------------

    def _submit(
        self,
        side: Side,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
    ) -> Tuple[Optional[Order], list]:
        """
        Build and submit an order. Returns (order, trades) on success,
        (None, []) if construction or submission raised any exception.
        """
        try:
            order = Order(
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            )
            trades = self._engine.submit_order(order)
            return order, trades
        except Exception as exc:
            logger.debug("[%s] submit failed: %s", self.name, exc)
            return None, []

    def _cancel(self, order_id: str) -> bool:
        """
        Cancel an order by ID. Returns True if cancelled.
        Returns False — without raising — if the order was already filled
        (ValueError) or is not in the book (KeyError). Both cases are routine:
        they mean the market maker's quote was hit, which is expected behavior.
        """
        try:
            self._engine.cancel_order(order_id)
            return True
        except (KeyError, ValueError):
            return False

    def _mid_price(self, snap: dict) -> Optional[float]:
        """
        Best-bid/best-ask midpoint.
        Falls back to most recent trade price if one side is empty.
        Returns None only when the book has no quotes and no trade history.
        """
        bids = snap.get("bids", [])
        asks = snap.get("asks", [])
        if bids and asks:
            return (bids[0]["price"] + asks[0]["price"]) / 2.0
        trades = snap.get("recent_trades", [])
        if trades:
            return float(trades[-1]["price"])
        return None


# ---------------------------------------------------------------------------
# Step 2 — NoiseTrader
# ---------------------------------------------------------------------------

class NoiseTrader(BaseAgent):
    """
    Submits random limit orders near the current mid-price.

    Price is drawn from a Gaussian centered on a blend of the current mid
    and target_price. The blend (mean_revert_weight) is the fraction of
    target_price in that mix — higher values pull the reference price back
    toward target on each tick, preventing the book from drifting over time.

    Ticks at 0.5 s by default (configurable). No internal state between ticks.
    """

    def __init__(
        self,
        engine: MatchingEngine,
        name: str = "noise",
        target_price: float = 100.0,
        tick_interval: float = 0.5,
        price_sigma: float = 0.015,        # Gaussian std dev as fraction of ref price
        qty_min: float = 1.0,
        qty_max: float = 15.0,
        mean_revert_weight: float = 0.25,  # 0 = pure mid, 1 = pure target_price
    ) -> None:
        super().__init__(engine, name, target_price, tick_interval)
        self.price_sigma = price_sigma
        self.qty_min = qty_min
        self.qty_max = qty_max
        self.mean_revert_weight = mean_revert_weight

    async def tick(self) -> None:
        snap = self._engine.snapshot()
        mid = self._mid_price(snap)

        # Blend mid with target to prevent long-run drift
        if mid is not None:
            ref = mid * (1.0 - self.mean_revert_weight) + self.target_price * self.mean_revert_weight
        else:
            ref = self.target_price

        price = round(ref * (1.0 + random.gauss(0.0, self.price_sigma)), 2)
        price = max(0.01, price)

        qty = round(random.uniform(self.qty_min, self.qty_max), 2)
        side = random.choice([Side.BUY, Side.SELL])

        self._submit(side, OrderType.LIMIT, qty, price)


# ---------------------------------------------------------------------------
# Step 3 — MarketMaker
# ---------------------------------------------------------------------------

class MarketMaker(BaseAgent):
    """
    Continuously posts a two-sided limit-order quote around the mid-price.

    Every tick the market maker:
      1. Cancels its outstanding bid and ask (if any).
      2. Computes a fresh reference price.
      3. Posts a new bid at ref*(1 - half_spread) and ask at ref*(1 + half_spread).
      4. Records the new order IDs for cancellation next tick.

    "Getting run over" — a large market order that fills the quote entirely:
      Step 1's _cancel() call returns False (the order is already gone from
      the book). This is caught silently; the market maker simply skips the
      cancel and immediately resets its tracked IDs to None before posting
      fresh quotes. There is no exception, no crash, no stuck state.

    If a quote is partially filled (status == PARTIAL), the market maker still
    cancels the remainder so every tick starts with a clean slate. This prevents
    stale quotes from lingering at off-market prices.

    Falls back to target_price when the book is empty so it can bootstrap the
    simulation from scratch without needing seed orders.

    Ticks every 25 ms by default, satisfying the <50 ms latency requirement.
    """

    def __init__(
        self,
        engine: MatchingEngine,
        name: str = "mm",
        target_price: float = 100.0,
        tick_interval: float = 0.025,
        spread: float = 0.004,     # full spread as fraction of price (e.g. 0.4%)
        quote_qty: float = 10.0,
    ) -> None:
        super().__init__(engine, name, target_price, tick_interval)
        self.half_spread = spread / 2.0
        self.quote_qty = quote_qty
        self._bid_id: Optional[str] = None
        self._ask_id: Optional[str] = None

    async def tick(self) -> None:
        # --- Cancel previous quotes ---
        # _cancel() returns False for already-filled orders — that's "getting
        # run over" and is handled transparently here. We always clear the IDs
        # so the next block starts with a clean slate regardless.
        if self._bid_id:
            self._cancel(self._bid_id)
            self._bid_id = None
        if self._ask_id:
            self._cancel(self._ask_id)
            self._ask_id = None

        # --- Compute fresh prices ---
        ref = self._ref_price()
        bid_price = round(ref * (1.0 - self.half_spread), 2)
        ask_price = round(ref * (1.0 + self.half_spread), 2)

        # Guard: spread must be positive and prices must be valid
        if bid_price <= 0.0 or ask_price <= bid_price:
            return

        # --- Post fresh quotes ---
        bid, _ = self._submit(Side.BUY, OrderType.LIMIT, self.quote_qty, bid_price)
        ask, _ = self._submit(Side.SELL, OrderType.LIMIT, self.quote_qty, ask_price)

        # Track only orders that are resting on the book (not instantly filled)
        if bid and bid.status in (OrderStatus.OPEN, OrderStatus.PARTIAL):
            self._bid_id = bid.order_id
        if ask and ask.status in (OrderStatus.OPEN, OrderStatus.PARTIAL):
            self._ask_id = ask.order_id

    def _ref_price(self) -> float:
        """
        Mid-price if both sides are quoted, else last trade price, else target_price.

        target_price as the final fallback is what prevents the market from
        drifting to zero or infinity when the book is thin or one-sided.
        """
        snap = self._engine.snapshot()
        mid = self._mid_price(snap)
        return mid if mid is not None else self.target_price

    def status(self) -> dict:
        s = super().status()
        s["bid_id"] = self._bid_id
        s["ask_id"] = self._ask_id
        s["half_spread_pct"] = round(self.half_spread * 100, 4)
        s["quote_qty"] = self.quote_qty
        return s


# ---------------------------------------------------------------------------
# Step 4 — MomentumTrader
# ---------------------------------------------------------------------------

class MomentumTrader(BaseAgent):
    """
    Follows recent trade direction using a two-window momentum signal.

    Logic per tick
    --------------
    1. Enforce cooldown — skip if we traded too recently.
    2. Fetch the last `lookback` trades from the engine snapshot.
    3. Mean-reversion override: if the current price has drifted more than
       drift_tolerance (%) from target_price, trade against the drift regardless
       of momentum. This is the primary mechanism that prevents the simulation
       from running away to zero or infinity.
    4. Momentum signal: split the lookback window in half, compare early avg
       vs. late avg. Buy if price is trending up, sell if trending down.
    5. Submit a market order in the chosen direction and reset the cooldown timer.

    Uses market orders (not limit orders) so fills are immediate and there are
    no resting positions to manage between ticks.

    Ticks every 25 ms by default. The cooldown (default 3 s) means the agent
    trades at most once every 3 s regardless of tick rate.
    """

    def __init__(
        self,
        engine: MatchingEngine,
        name: str = "momentum",
        target_price: float = 100.0,
        tick_interval: float = 0.025,
        lookback: int = 10,
        cooldown: float = 3.0,
        trade_qty: float = 5.0,
        drift_tolerance: float = 0.03,   # 3% from target triggers mean-reversion
    ) -> None:
        super().__init__(engine, name, target_price, tick_interval)
        self.lookback = lookback
        self.cooldown = cooldown
        self.trade_qty = trade_qty
        self.drift_tolerance = drift_tolerance
        self._last_trade_ts: float = 0.0

    async def tick(self) -> None:
        now = time.monotonic()
        if now - self._last_trade_ts < self.cooldown:
            return

        snap = self._engine.snapshot()
        recent_trades = snap.get("recent_trades", [])

        if len(recent_trades) < self.lookback:
            return  # not enough history yet

        prices = [float(t["price"]) for t in recent_trades[-self.lookback:]]
        current_price = prices[-1]

        # --- Mean-reversion override ---
        # If price has drifted too far from the anchor, trade back toward it.
        # This takes priority over the momentum signal.
        drift = (current_price - self.target_price) / self.target_price
        if drift > self.drift_tolerance:
            side = Side.SELL
        elif drift < -self.drift_tolerance:
            side = Side.BUY
        else:
            # --- Momentum signal ---
            mid = len(prices) // 2
            early_avg = sum(prices[:mid]) / mid
            late_avg = sum(prices[mid:]) / (len(prices) - mid)

            if late_avg > early_avg:
                side = Side.BUY
            elif late_avg < early_avg:
                side = Side.SELL
            else:
                return  # flat — no signal

        order, _ = self._submit(side, OrderType.MARKET, self.trade_qty)
        if order:
            self._last_trade_ts = now

    def status(self) -> dict:
        s = super().status()
        elapsed = time.monotonic() - self._last_trade_ts
        s["cooldown_remaining_s"] = round(max(0.0, self.cooldown - elapsed), 2)
        s["drift_tolerance_pct"] = round(self.drift_tolerance * 100, 2)
        return s


# ---------------------------------------------------------------------------
# Step 5 — RLAgent (inference-only, trained DQN)
# ---------------------------------------------------------------------------

class RLAgent(BaseAgent):
    """
    Runs the trained DQN policy in inference mode against the live book.

    No gradient updates happen here — training is handled separately by
    TrainingSession.  The agent reuses TradingEnv for observation building
    and order execution so the live behaviour exactly matches training.

    Episode semantics: the agent runs continuous episodes.  When the position
    limit is hit (or after max_steps ticks), the env resets (pending orders
    are cancelled, position/cash zeroed) and a new episode begins.  Cumulative
    PnL across episodes is tracked and reported via status().

    If no checkpoint exists the agent ticks silently without trading until
    one becomes available on the next episode reset.
    """

    _ACTION_NAMES = ["hold", "buy_mkt", "sell_mkt", "buy_lim", "sell_lim", "cancel"]

    def __init__(
        self,
        engine: MatchingEngine,
        name: str = "rl",
        target_price: float = 100.0,
        tick_interval: float = 0.025,
        max_steps_per_episode: int = 500,
    ) -> None:
        super().__init__(engine, name, target_price, tick_interval)

        if not _check_rl():
            raise RuntimeError("RLAgent requires torch — run: pip install torch")

        from rl.agent import DQNAgent
        from rl.env import TradingEnv
        from rl.train import CHECKPOINT_FILE

        self._env = TradingEnv(engine, target_price=target_price, max_steps=max_steps_per_episode)
        self._dqn = DQNAgent()
        self._ready = False
        self._ckpt_path = CHECKPOINT_FILE

        self._last_action: int = 0
        self._total_episodes: int = 0
        self._episode_pnl: float = 0.0
        self._cumulative_pnl: float = 0.0

        self._try_load()
        self._env.reset()

    def _try_load(self) -> None:
        if self._ckpt_path.exists():
            try:
                self._dqn.load(str(self._ckpt_path))
                self._ready = True
                logger.info("[%s] Loaded RL checkpoint", self.name)
            except Exception as exc:
                logger.warning("[%s] Could not load checkpoint: %s", self.name, exc)
        else:
            logger.warning("[%s] No checkpoint found — sitting idle until trained", self.name)

    async def tick(self) -> None:
        # Retry loading checkpoint each episode if not yet ready
        if not self._ready:
            self._try_load()
            if not self._ready:
                return

        obs = self._env._observe()
        action = self._dqn.select_action(obs, exploit=True)
        _, reward, done, info = self._env.step(action)

        self._last_action = action
        self._episode_pnl = info["mtm"]

        if done:
            self._cumulative_pnl += self._episode_pnl
            self._total_episodes += 1
            self._env.reset()

    def status(self) -> dict:
        s = super().status()
        s["last_action"] = self._ACTION_NAMES[self._last_action]
        s["position"] = round(self._env.position, 2)
        s["episode_pnl"] = round(self._episode_pnl, 4)
        s["cumulative_pnl"] = round(self._cumulative_pnl, 4)
        s["total_episodes"] = self._total_episodes
        s["ready"] = self._ready
        return s
