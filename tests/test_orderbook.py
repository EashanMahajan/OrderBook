"""
test_orderbook.py — Unit tests for the OrderBook data structure.

Validates add/cancel operations, heap ordering, lazy deletion,
price-time priority, snapshot generation, and edge cases.
"""

import pytest
from time import sleep

from engine.order import Order, Side, OrderType, OrderStatus
from engine.orderbook import OrderBook

class TestAddOrder:
    def test_add_limit_buy(self):
        book = OrderBook()
        order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0)
        book.add_order(order)

        assert book.bid_count == 1
        assert book.ask_count == 0
        assert book.get_order(order.order_id) is order

    def test_add_limit_sell(self):
        book = OrderBook()
        order = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=5.0)
        book.add_order(order)

        assert book.ask_count == 1
        assert book.bid_count == 0
        assert book.get_order(order.order_id) is order

    def test_add_multiple_orders(self):
        book = OrderBook()
        for i in range(5):
            book.add_order(
                Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0 + i, quantity=1.0)
            )
            book.add_order(
                Order(side=Side.SELL, order_type=OrderType.LIMIT, price=110.0 + i, quantity=1.0)
            )
        assert book.bid_count == 5
        assert book.ask_count == 5

    def test_reject_market_order(self):
        book = OrderBook()
        order = Order(side=Side.BUY, order_type=OrderType.MARKET, quantity=10.0)
        with pytest.raises(ValueError, match="Market orders"):
            book.add_order(order)

    def test_reject_duplicate_order_id(self):
        book = OrderBook()
        order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0)
        book.add_order(order)
        with pytest.raises(ValueError, match="Duplicate"):
            book.add_order(order)

class TestBestBidAsk:
    def test_best_bid(self):
        book = OrderBook()
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=99.0, quantity=1.0))
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=101.0, quantity=1.0))
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0))

        best = book.best_bid()
        assert best is not None
        assert best.price == 101.0

    def test_best_ask(self):
        book = OrderBook()
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=1.0))
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=103.0, quantity=1.0))
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=107.0, quantity=1.0))

        best = book.best_ask()
        assert best is not None
        assert best.price == 103.0

    def test_empty_book_returns_none(self):
        book = OrderBook()
        assert book.best_bid() is None
        assert book.best_ask() is None

    def test_best_bid_skips_cancelled(self):
        """Lazy deletion: cancelled orders at top are cleaned up."""
        book = OrderBook()
        o1 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=101.0, quantity=1.0)
        o2 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0)
        book.add_order(o1)
        book.add_order(o2)

        book.cancel_order(o1.order_id)
        best = book.best_bid()
        assert best is not None
        assert best.price == 100.0

    def test_best_ask_skips_filled(self):
        """Lazy deletion: filled orders at top are cleaned up."""
        book = OrderBook()
        o1 = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=103.0, quantity=5.0)
        o2 = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=5.0)
        book.add_order(o1)
        book.add_order(o2)

        # Simulate the matching engine fully filling the best ask
        o1.fill(5.0)
        best = book.best_ask()
        assert best is not None
        assert best.price == 105.0

    def test_all_cancelled_returns_none(self):
        book = OrderBook()
        o1 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0)
        o2 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=99.0, quantity=1.0)
        book.add_order(o1)
        book.add_order(o2)
        book.cancel_order(o1.order_id)
        book.cancel_order(o2.order_id)

        assert book.best_bid() is None

class TestCancelOrder:
    def test_cancel_open_order(self):
        book = OrderBook()
        order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0)
        book.add_order(order)

        cancelled = book.cancel_order(order.order_id)
        assert cancelled.status == OrderStatus.CANCELLED
        assert cancelled is order

    def test_cancel_partial_order(self):
        book = OrderBook()
        order = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=10.0)
        book.add_order(order)
        order.fill(3.0)

        cancelled = book.cancel_order(order.order_id)
        assert cancelled.status == OrderStatus.CANCELLED

    def test_cancel_unknown_id_raises(self):
        book = OrderBook()
        with pytest.raises(KeyError, match="not found"):
            book.cancel_order("nonexistent-id")

    def test_cancel_filled_raises(self):
        book = OrderBook()
        order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0)
        book.add_order(order)
        order.fill(10.0)

        with pytest.raises(ValueError, match="filled"):
            book.cancel_order(order.order_id)

class TestPriceTimePriority:
    def test_bids_higher_price_wins(self):
        book = OrderBook()
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=99.0, quantity=1.0))
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=101.0, quantity=1.0))

        assert book.best_bid().price == 101.0

    def test_asks_lower_price_wins(self):
        book = OrderBook()
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=107.0, quantity=1.0))
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=103.0, quantity=1.0))

        assert book.best_ask().price == 103.0

    def test_same_price_earlier_timestamp_wins(self):
        """At the same price, the order placed first has priority."""
        book = OrderBook()
        first = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0)
        sleep(0.01)  # ensure distinct timestamps
        second = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0)

        book.add_order(second)  # add second first to prove timestamp wins
        book.add_order(first)

        assert book.best_bid().order_id == first.order_id

    def test_same_price_earlier_timestamp_wins_asks(self):
        book = OrderBook()
        first = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=1.0)
        sleep(0.01)
        second = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=1.0)

        book.add_order(second)
        book.add_order(first)

        assert book.best_ask().order_id == first.order_id

class TestSnapshot:
    def test_empty_snapshot(self):
        book = OrderBook()
        snap = book.snapshot()
        assert snap["bids"] == []
        assert snap["asks"] == []
        assert snap["spread"] is None
        assert snap["bid_count"] == 0
        assert snap["ask_count"] == 0

    def test_aggregation_by_price_level(self):
        book = OrderBook()
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0))
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=5.0))
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=99.0, quantity=3.0))

        snap = book.snapshot()
        assert len(snap["bids"]) == 2  # two price levels

        # Best bid level first (descending)
        top_level = snap["bids"][0]
        assert top_level["price"] == 100.0
        assert top_level["total_quantity"] == 15.0
        assert top_level["order_count"] == 2

    def test_spread_calculation(self):
        book = OrderBook()
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0))
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=101.50, quantity=1.0))

        snap = book.snapshot()
        assert snap["spread"] == 1.50

    def test_snapshot_excludes_cancelled(self):
        book = OrderBook()
        o1 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0)
        o2 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=5.0)
        book.add_order(o1)
        book.add_order(o2)

        book.cancel_order(o1.order_id)
        snap = book.snapshot()

        assert len(snap["bids"]) == 1
        assert snap["bids"][0]["total_quantity"] == 5.0
        assert snap["bids"][0]["order_count"] == 1
        assert snap["bid_count"] == 1

    def test_snapshot_excludes_filled(self):
        book = OrderBook()
        order = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=10.0)
        book.add_order(order)
        order.fill(10.0)

        snap = book.snapshot()
        assert snap["asks"] == []
        assert snap["ask_count"] == 0

    def test_snapshot_uses_remaining_quantity(self):
        """Partially filled orders contribute their remaining qty, not original."""
        book = OrderBook()
        order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0)
        book.add_order(order)
        order.fill(3.0)

        snap = book.snapshot()
        assert snap["bids"][0]["total_quantity"] == 7.0

    def test_bids_descending_asks_ascending(self):
        book = OrderBook()
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=98.0, quantity=1.0))
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0))
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=99.0, quantity=1.0))

        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=1.0))
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=103.0, quantity=1.0))
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=107.0, quantity=1.0))

        snap = book.snapshot()
        bid_prices = [lvl["price"] for lvl in snap["bids"]]
        ask_prices = [lvl["price"] for lvl in snap["asks"]]

        assert bid_prices == [100.0, 99.0, 98.0]  # descending
        assert ask_prices == [103.0, 105.0, 107.0]  # ascending

class TestSpread:
    def test_spread_with_both_sides(self):
        book = OrderBook()
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0))
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=102.0, quantity=1.0))

        assert book.spread == 2.0

    def test_spread_no_bids(self):
        book = OrderBook()
        book.add_order(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=105.0, quantity=1.0))
        assert book.spread is None

    def test_spread_no_asks(self):
        book = OrderBook()
        book.add_order(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0))
        assert book.spread is None

class TestEdgeCases:
    def test_single_order_book(self):
        book = OrderBook()
        order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=1.0)
        book.add_order(order)

        assert book.best_bid() is order
        assert book.best_ask() is None
        assert book.spread is None

    def test_cancel_then_add_at_same_price(self):
        book = OrderBook()
        o1 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=5.0)
        book.add_order(o1)
        book.cancel_order(o1.order_id)

        o2 = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, quantity=10.0)
        book.add_order(o2)

        assert book.best_bid() is o2
        assert book.bid_count == 1

    def test_get_nonexistent_order(self):
        book = OrderBook()
        assert book.get_order("does-not-exist") is None

    def test_heavy_load(self):
        """Smoke test with 1000 orders per side."""
        book = OrderBook()
        for i in range(1000):
            book.add_order(
                Order(side=Side.BUY, order_type=OrderType.LIMIT,
                      price=90.0 + (i % 20) * 0.5, quantity=1.0)
            )
            book.add_order(
                Order(side=Side.SELL, order_type=OrderType.LIMIT,
                      price=110.0 + (i % 20) * 0.5, quantity=1.0)
            )

        assert book.bid_count == 1000
        assert book.ask_count == 1000
        assert book.best_bid().price == 99.5   # 90.0 + 19 * 0.5
        assert book.best_ask().price == 110.0

        snap = book.snapshot()
        assert len(snap["bids"]) == 20   # 20 distinct price levels
        assert len(snap["asks"]) == 20

    def test_lazy_deletion_chain(self):
        """Multiple cancelled orders stacked at the top are all cleaned."""
        book = OrderBook()
        orders = []
        for price in [103.0, 102.0, 101.0, 100.0]:
            o = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=price, quantity=1.0)
            book.add_order(o)
            orders.append(o)

        # Cancel top 3
        book.cancel_order(orders[0].order_id)  # 103
        book.cancel_order(orders[1].order_id)  # 102
        book.cancel_order(orders[2].order_id)  # 101

        best = book.best_bid()
        assert best is not None
        assert best.price == 100.0
