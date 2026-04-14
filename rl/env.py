"""
TradingEnv — gym-style MDP wrapper around the MatchingEngine.

MDP definition (Step 1 — refined)
-----------------------------------
State (STATE_DIM = 15):
  [0]    best_bid / target_price            (0 if no bid)
  [1]    best_ask / target_price            (0 if no ask)
  [2]    spread / target_price              (0 if one side empty)
  [3-5]  top-3 bid total_quantities / 50   (0-padded)
  [6-8]  top-3 ask total_quantities / 50   (0-padded)
  [9]    price momentum over last 10 trades / target_price
  [10]   recent trade count / 20           (saturation at 1.0)
  [11]   agent position / MAX_POSITION     (clipped to [-1, 1])
  [12]   mark-to-market / (target * MAX_POSITION)
  [13]   cash / (target * MAX_POSITION)
  [14]   step_num / max_steps

Actions (N_ACTIONS = 6):
  0  HOLD            — do nothing
  1  BUY_MARKET      — buy TRADE_QTY at market
  2  SELL_MARKET     — sell TRADE_QTY at market
  3  BUY_LIMIT       — post limit buy at current best bid
  4  SELL_LIMIT      — post limit sell at current best ask
  5  CANCEL_ALL      — cancel all of the agent's resting limit orders

Reward:
  Δ(mark-to-market) - INVENTORY_PENALTY * |position|

Episode ends when |position| >= MAX_POSITION or step_num >= max_steps.
The engine is NEVER flushed on reset — only the agent's tracking state is
cleared.  The RL agent trains in a live shared market with other agents.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from engine.matching_engine import MatchingEngine
from engine.order import Order, OrderStatus, OrderType, Side

# MDP constants
STATE_DIM = 15
N_ACTIONS = 6

_MAX_QTY_NORM = 50.0   # normaliser for order-book quantities
MAX_POSITION = 50.0    # episode terminates if |position| hits this
TRADE_QTY = 5.0        # fixed lot size per market/limit order
INVENTORY_PENALTY = 0.02  # per-step cost per unit of open position


class TradingEnv:
    """Gym-style environment wrapping the order-book matching engine."""

    # Action indices (use these names instead of magic numbers)
    HOLD = 0
    BUY_MARKET = 1
    SELL_MARKET = 2
    BUY_LIMIT = 3
    SELL_LIMIT = 4
    CANCEL_ALL = 5

    def __init__(
        self,
        engine: MatchingEngine,
        target_price: float = 100.0,
        max_steps: int = 500,
        trade_qty: float = TRADE_QTY,
        inventory_penalty: float = INVENTORY_PENALTY,
    ) -> None:
        self.engine = engine
        self.target_price = target_price
        self.max_steps = max_steps
        self.trade_qty = trade_qty
        self.inventory_penalty = inventory_penalty

        # Agent-owned state — zeroed by reset()
        self.position: float = 0.0   # shares held (+ long, − short)
        self.cash: float = 0.0       # running cash balance
        self.step_num: int = 0
        self._pending_ids: list[str] = []

    # ------------------------------------------------------------------
    # Gym interface
    # ------------------------------------------------------------------

    def reset(self) -> np.ndarray:
        """Cancel any resting agent orders, zero state, return initial obs."""
        self._cancel_pending()
        self.position = 0.0
        self.cash = 0.0
        self.step_num = 0
        return self._observe()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, dict]:
        """
        Execute action, advance one step.

        Returns
        -------
        obs        : np.ndarray of shape (STATE_DIM,)
        reward     : float
        done       : bool
        info       : dict with position, cash, mtm, step
        """
        prev_mtm = self._mark_to_market()
        self._execute(action)
        self.step_num += 1

        new_mtm = self._mark_to_market()
        reward = (new_mtm - prev_mtm) - self.inventory_penalty * abs(self.position)

        done = abs(self.position) >= MAX_POSITION or self.step_num >= self.max_steps
        obs = self._observe()
        info = {
            "position": self.position,
            "cash": self.cash,
            "mtm": new_mtm,
            "step": self.step_num,
        }
        return obs, reward, done, info

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute(self, action: int) -> None:
        snap = self.engine.snapshot()
        bids = snap.get("bids", [])
        asks = snap.get("asks", [])

        if action == self.HOLD:
            return

        elif action == self.BUY_MARKET:
            _, trades = self._submit(Side.BUY, OrderType.MARKET, self.trade_qty)
            for t in trades:
                self.position += t.quantity
                self.cash -= t.price * t.quantity

        elif action == self.SELL_MARKET:
            _, trades = self._submit(Side.SELL, OrderType.MARKET, self.trade_qty)
            for t in trades:
                self.position -= t.quantity
                self.cash += t.price * t.quantity

        elif action == self.BUY_LIMIT:
            if not bids:
                return
            order, trades = self._submit(Side.BUY, OrderType.LIMIT, self.trade_qty, bids[0]["price"])
            if order and order.status in (OrderStatus.OPEN, OrderStatus.PARTIAL):
                self._pending_ids.append(order.order_id)
            for t in trades:
                self.position += t.quantity
                self.cash -= t.price * t.quantity

        elif action == self.SELL_LIMIT:
            if not asks:
                return
            order, trades = self._submit(Side.SELL, OrderType.LIMIT, self.trade_qty, asks[0]["price"])
            if order and order.status in (OrderStatus.OPEN, OrderStatus.PARTIAL):
                self._pending_ids.append(order.order_id)
            for t in trades:
                self.position -= t.quantity
                self.cash += t.price * t.quantity

        elif action == self.CANCEL_ALL:
            self._cancel_pending()

    def _submit(
        self,
        side: Side,
        order_type: OrderType,
        qty: float,
        price: Optional[float] = None,
    ):
        try:
            order = Order(side=side, order_type=order_type, quantity=qty, price=price)
            trades = self.engine.submit_order(order)
            return order, trades
        except Exception:
            return None, []

    def _cancel_pending(self) -> None:
        for oid in self._pending_ids:
            try:
                self.engine.cancel_order(oid)
            except (KeyError, ValueError):
                pass
        self._pending_ids.clear()

    def _mark_to_market(self) -> float:
        snap = self.engine.snapshot()
        bids = snap.get("bids", [])
        asks = snap.get("asks", [])
        trades = snap.get("recent_trades", [])

        if bids and asks:
            mid = (bids[0]["price"] + asks[0]["price"]) / 2.0
        elif bids:
            mid = bids[0]["price"]
        elif asks:
            mid = asks[0]["price"]
        elif trades:
            mid = trades[-1]["price"]
        else:
            mid = self.target_price

        return self.cash + self.position * mid

    def _observe(self) -> np.ndarray:
        snap = self.engine.snapshot()
        bids = snap.get("bids", [])
        asks = snap.get("asks", [])
        recent = snap.get("recent_trades", [])
        tp = self.target_price

        # Price / spread features
        best_bid = bids[0]["price"] / tp if bids else 0.0
        best_ask = asks[0]["price"] / tp if asks else 0.0
        spread = ((asks[0]["price"] - bids[0]["price"]) / tp) if (bids and asks) else 0.0

        # Top-3 depth quantities (0-padded)
        bid_qtys = [bids[i]["total_quantity"] / _MAX_QTY_NORM if i < len(bids) else 0.0 for i in range(3)]
        ask_qtys = [asks[i]["total_quantity"] / _MAX_QTY_NORM if i < len(asks) else 0.0 for i in range(3)]

        # Trade flow features
        if len(recent) >= 2:
            momentum = (recent[-1]["price"] - recent[max(0, len(recent) - 10)]["price"]) / tp
        else:
            momentum = 0.0
        trade_count_norm = min(len(recent) / 20.0, 1.0)

        # Agent state features
        pos_norm = float(np.clip(self.position / MAX_POSITION, -1.0, 1.0))
        mtm_norm = float(np.clip(self._mark_to_market() / (tp * MAX_POSITION), -2.0, 2.0))
        cash_norm = float(np.clip(self.cash / (tp * MAX_POSITION), -2.0, 2.0))
        step_frac = self.step_num / self.max_steps

        obs = np.array([
            best_bid, best_ask, spread,
            *bid_qtys, *ask_qtys,
            momentum, trade_count_norm,
            pos_norm, mtm_norm, cash_norm,
            step_frac,
        ], dtype=np.float32)

        assert len(obs) == STATE_DIM
        return obs
