"""
orderbook.py — Maintains the live bid and ask sides of the order book.

Uses heap-based data structures for O(log n) insertion and O(1) best-price
access. Bids use a max-heap (negated prices in Python's min-heap).
Asks use a natural min-heap. Cancelled orders use lazy deletion.
"""

from __future__ import annotations

import heapq
from typing import Optional

from engine.order import Order, OrderStatus, OrderType, Side


class _BidEntry:
    """
    Wraps an Order for the bid-side max-heap.

    Python's heapq is a min-heap, so we negate the price to get max-heap
    behavior (highest bid = best). Ties broken by timestamp (earlier wins).
    """

    __slots__ = ("neg_price", "timestamp", "order")

    def __init__(self, order: Order) -> None:
        self.neg_price = -order.price
        self.timestamp = order.timestamp
        self.order = order

    def __lt__(self, other: _BidEntry) -> bool:
        if self.neg_price != other.neg_price:
            return self.neg_price < other.neg_price
        return self.timestamp < other.timestamp


class _AskEntry:
    """
    Wraps an Order for the ask-side min-heap.

    Natural min-heap — lowest ask price = best. Ties broken by timestamp.
    """

    __slots__ = ("price", "timestamp", "order")

    def __init__(self, order: Order) -> None:
        self.price = order.price
        self.timestamp = order.timestamp
        self.order = order

    def __lt__(self, other: _AskEntry) -> bool:
        if self.price != other.price:
            return self.price < other.price
        return self.timestamp < other.timestamp


class OrderBook:
    """
    A price-time priority order book for a single instrument.

    Maintains two heaps (bids and asks) and a lookup dict for O(1) access
    by order ID. Supports add, cancel, best-price queries, and snapshot
    generation for API/WebSocket consumers.

    Cancelled and filled orders are cleaned up lazily — they remain in the
    heap until they surface to the top during best_bid()/best_ask() calls.
    """

    def __init__(self) -> None:
        self._bids: list[_BidEntry] = []
        self._asks: list[_AskEntry] = []
        self._orders: dict[str, Order] = {}

    @property
    def bid_count(self) -> int:
        """Number of live (open/partial) buy orders."""
        return sum(
            1 for o in self._orders.values()
            if o.side == Side.BUY and o.status in (OrderStatus.OPEN, OrderStatus.PARTIAL)
        )

    @property
    def ask_count(self) -> int:
        """Number of live (open/partial) sell orders."""
        return sum(
            1 for o in self._orders.values()
            if o.side == Side.SELL and o.status in (OrderStatus.OPEN, OrderStatus.PARTIAL)
        )

    @property
    def spread(self) -> Optional[float]:
        """
        Current bid-ask spread, or None if either side is empty.
        """
        bb = self.best_bid()
        ba = self.best_ask()
        if bb is None or ba is None:
            return None
        return round(ba.price - bb.price, 10)

    def add_order(self, order: Order) -> None:
        """
        Add a limit order to the book.

        Market orders should NOT be added to the book — they are consumed
        immediately by the matching engine. Raises ValueError if a market
        order is passed.
        """
        if order.order_type == OrderType.MARKET:
            raise ValueError(
                "Market orders cannot rest on the book — "
                "route them through the matching engine"
            )

        if order.order_id in self._orders:
            raise ValueError(f"Duplicate order ID: {order.order_id}")

        self._orders[order.order_id] = order

        if order.side == Side.BUY:
            heapq.heappush(self._bids, _BidEntry(order))
        else:
            heapq.heappush(self._asks, _AskEntry(order))

    def cancel_order(self, order_id: str) -> Order:
        """
        Cancel an order by ID. Uses lazy deletion — the order is marked
        as cancelled but remains in the heap until it surfaces to the top.

        Returns the cancelled Order. Raises KeyError if ID not found.
        """
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(f"Order not found: {order_id}")

        order.cancel()  # raises ValueError if already filled
        return order

    def best_bid(self) -> Optional[Order]:
        """
        Return the highest-priority buy order, or None if no bids exist.

        Lazily removes cancelled/filled orders that have surfaced to the top.
        """
        return self._peek_best(self._bids)

    def best_ask(self) -> Optional[Order]:
        """
        Return the highest-priority sell order, or None if no asks exist.

        Lazily removes cancelled/filled orders that have surfaced to the top.
        """
        return self._peek_best(self._asks)

    def get_order(self, order_id: str) -> Optional[Order]:
        """Look up an order by ID. Returns None if not found."""
        return self._orders.get(order_id)

    def snapshot(self) -> dict:
        """
        Return the current state of the book, aggregated by price level.

        Returns a dict with:
            - bids: list of {price, total_quantity, order_count}, descending
            - asks: list of {price, total_quantity, order_count}, ascending
            - spread: float or None
            - bid_count: total live buy orders
            - ask_count: total live sell orders
        """
        bid_levels = self._aggregate_levels(Side.BUY)
        ask_levels = self._aggregate_levels(Side.SELL)

        # Sort bids descending (best bid first), asks ascending (best ask first)
        bid_levels.sort(key=lambda lvl: lvl["price"], reverse=True)
        ask_levels.sort(key=lambda lvl: lvl["price"])

        return {
            "bids": bid_levels,
            "asks": ask_levels,
            "spread": self.spread,
            "bid_count": self.bid_count,
            "ask_count": self.ask_count,
        }

    @staticmethod
    def _is_live(order: Order) -> bool:
        """Check if an order is still active (open or partially filled)."""
        return order.status in (OrderStatus.OPEN, OrderStatus.PARTIAL)

    def _peek_best(self, heap: list) -> Optional[Order]:
        """
        Peek at the best order on a heap side, lazily cleaning dead entries.
        """
        while heap:
            entry = heap[0]
            order = entry.order
            if self._is_live(order):
                return order
            # Dead order — pop and discard
            heapq.heappop(heap)
        return None

    def _aggregate_levels(self, side: Side) -> list[dict]:
        """
        Aggregate live orders by price level for the given side.
        """
        levels: dict[float, dict] = {}

        for order in self._orders.values():
            if order.side != side or not self._is_live(order):
                continue

            price = order.price
            if price not in levels:
                levels[price] = {
                    "price": price,
                    "total_quantity": 0.0,
                    "order_count": 0,
                }
            levels[price]["total_quantity"] += order.remaining
            levels[price]["order_count"] += 1

        return list(levels.values())
