"""
order.py — Core data structures for the order book simulator.

Defines the Order and Trade dataclasses that serve as the fundamental
primitives throughout the system. Every other module depends on these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Optional

from ulid import ULID


class Side(str, Enum):
    """Order side — buy or sell."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type — limit (has price) or market (takes best available)."""
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    """Lifecycle status of an order."""
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """
    Represents a single order submitted to the matching engine.

    Attributes:
        order_id:   Unique identifier (ULID — sortable, collision-free).
        side:       Buy or sell.
        order_type: Limit or market.
        price:      Limit price. None for market orders.
        quantity:    Original quantity requested.
        remaining:  Quantity still unfilled (starts equal to quantity).
        timestamp:  Epoch time of order creation — used for time priority.
        status:     Current lifecycle status.
    """

    side: Side
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    order_id: str = field(default_factory=lambda: str(ULID()))
    remaining: float = field(init=False)
    timestamp: float = field(default_factory=time)
    status: OrderStatus = OrderStatus.OPEN

    def __post_init__(self) -> None:
        # Remaining starts equal to quantity
        self.remaining = self.quantity

        # Validation
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")

        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Limit orders must specify a price")

        if self.order_type == OrderType.LIMIT and self.price <= 0:
            raise ValueError(f"Limit price must be positive, got {self.price}")

        if self.order_type == OrderType.MARKET and self.price is not None:
            raise ValueError("Market orders must not specify a price")

    def fill(self, qty: float) -> None:
        """Reduce remaining quantity by *qty*. Updates status accordingly."""
        if qty <= 0:
            raise ValueError(f"Fill quantity must be positive, got {qty}")
        if qty > self.remaining:
            raise ValueError(
                f"Fill qty {qty} exceeds remaining {self.remaining}"
            )

        self.remaining -= qty

        if self.remaining == 0:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIAL

    def cancel(self) -> None:
        """Mark order as cancelled."""
        if self.status == OrderStatus.FILLED:
            raise ValueError("Cannot cancel a fully filled order")
        self.status = OrderStatus.CANCELLED

    def __lt__(self, other: Order) -> bool:
        """
        Comparison for heap ordering.
        Buy side: higher price = higher priority (we negate in the heap).
        Sell side: lower price = higher priority (natural min-heap).
        Ties broken by timestamp (earlier = higher priority).
        """
        if self.price != other.price:
            return self.price < other.price
        return self.timestamp < other.timestamp


@dataclass
class Trade:
    """
    Represents an executed trade between two orders.

    Created by the matching engine whenever a buy and sell order
    are matched at an agreed price and quantity.

    Attributes:
        trade_id:       Unique identifier (ULID).
        buy_order_id:   ID of the buying order.
        sell_order_id:  ID of the selling order.
        price:          Execution price.
        quantity:        Executed quantity.
        timestamp:      Epoch time of execution.
    """

    buy_order_id: str
    sell_order_id: str
    price: float
    quantity: float
    trade_id: str = field(default_factory=lambda: str(ULID()))
    timestamp: float = field(default_factory=time)

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError(f"Trade price must be positive, got {self.price}")
        if self.quantity <= 0:
            raise ValueError(
                f"Trade quantity must be positive, got {self.quantity}"
            )
