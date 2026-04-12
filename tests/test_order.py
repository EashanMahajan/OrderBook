"""
test_order.py — Unit tests for Order and Trade dataclasses.

Validates creation, validation rules, fill/cancel behavior,
and edge cases for the core primitives.
"""

import pytest

from engine.order import Order, Trade, Side, OrderType, OrderStatus


# ===================================================================
# Order — Happy path
# ===================================================================

class TestOrderCreation:
    def test_limit_buy(self):
        order = Order(
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            price=100.0,
            quantity=10.0,
        )
        assert order.side == Side.BUY
        assert order.order_type == OrderType.LIMIT
        assert order.price == 100.0
        assert order.quantity == 10.0
        assert order.remaining == 10.0
        assert order.status == OrderStatus.OPEN
        assert order.order_id  # ULID should be generated

    def test_limit_sell(self):
        order = Order(
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=105.50,
            quantity=5.0,
        )
        assert order.side == Side.SELL
        assert order.price == 105.50

    def test_market_buy(self):
        order = Order(
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
        )
        assert order.price is None
        assert order.order_type == OrderType.MARKET

    def test_unique_ids(self):
        orders = [
            Order(side=Side.BUY, order_type=OrderType.MARKET, quantity=1.0)
            for _ in range(100)
        ]
        ids = {o.order_id for o in orders}
        assert len(ids) == 100


# ===================================================================
# Order — Validation / edge cases
# ===================================================================

class TestOrderValidation:
    def test_reject_zero_quantity(self):
        with pytest.raises(ValueError, match="positive"):
            Order(side=Side.BUY, order_type=OrderType.MARKET, quantity=0)

    def test_reject_negative_quantity(self):
        with pytest.raises(ValueError, match="positive"):
            Order(side=Side.BUY, order_type=OrderType.MARKET, quantity=-5)

    def test_reject_limit_without_price(self):
        with pytest.raises(ValueError, match="price"):
            Order(side=Side.BUY, order_type=OrderType.LIMIT, quantity=10)

    def test_reject_limit_with_zero_price(self):
        with pytest.raises(ValueError, match="positive"):
            Order(
                side=Side.BUY, order_type=OrderType.LIMIT,
                price=0, quantity=10,
            )

    def test_reject_market_with_price(self):
        with pytest.raises(ValueError, match="must not"):
            Order(
                side=Side.BUY, order_type=OrderType.MARKET,
                price=100, quantity=10,
            )


# ===================================================================
# Order — Fill behavior
# ===================================================================

class TestOrderFill:
    def test_full_fill(self):
        order = Order(
            side=Side.BUY, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        order.fill(10)
        assert order.remaining == 0
        assert order.status == OrderStatus.FILLED

    def test_partial_fill(self):
        order = Order(
            side=Side.BUY, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        order.fill(3)
        assert order.remaining == 7
        assert order.status == OrderStatus.PARTIAL

    def test_multiple_partial_fills(self):
        order = Order(
            side=Side.SELL, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        order.fill(3)
        order.fill(4)
        assert order.remaining == 3
        assert order.status == OrderStatus.PARTIAL
        order.fill(3)
        assert order.remaining == 0
        assert order.status == OrderStatus.FILLED

    def test_reject_overfill(self):
        order = Order(
            side=Side.BUY, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        with pytest.raises(ValueError, match="exceeds"):
            order.fill(11)

    def test_reject_zero_fill(self):
        order = Order(
            side=Side.BUY, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        with pytest.raises(ValueError, match="positive"):
            order.fill(0)


# ===================================================================
# Order — Cancel behavior
# ===================================================================

class TestOrderCancel:
    def test_cancel_open_order(self):
        order = Order(
            side=Side.BUY, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        order.cancel()
        assert order.status == OrderStatus.CANCELLED

    def test_cancel_partial_order(self):
        order = Order(
            side=Side.BUY, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        order.fill(5)
        order.cancel()
        assert order.status == OrderStatus.CANCELLED

    def test_reject_cancel_filled_order(self):
        order = Order(
            side=Side.BUY, order_type=OrderType.LIMIT,
            price=100, quantity=10,
        )
        order.fill(10)
        with pytest.raises(ValueError, match="filled"):
            order.cancel()


# ===================================================================
# Trade — Happy path
# ===================================================================

class TestTradeCreation:
    def test_basic_trade(self):
        trade = Trade(
            buy_order_id="buy-001",
            sell_order_id="sell-001",
            price=100.0,
            quantity=5.0,
        )
        assert trade.price == 100.0
        assert trade.quantity == 5.0
        assert trade.trade_id  # ULID generated

    def test_unique_trade_ids(self):
        trades = [
            Trade(
                buy_order_id="b", sell_order_id="s",
                price=100, quantity=1,
            )
            for _ in range(100)
        ]
        ids = {t.trade_id for t in trades}
        assert len(ids) == 100


# ===================================================================
# Trade — Validation
# ===================================================================

class TestTradeValidation:
    def test_reject_zero_price(self):
        with pytest.raises(ValueError, match="positive"):
            Trade(
                buy_order_id="b", sell_order_id="s",
                price=0, quantity=1,
            )

    def test_reject_negative_quantity(self):
        with pytest.raises(ValueError, match="positive"):
            Trade(
                buy_order_id="b", sell_order_id="s",
                price=100, quantity=-1,
            )


# ===================================================================
# FastAPI health check
# ===================================================================

class TestHealthCheck:
    @pytest.fixture
    def client(self):
        from httpx import AsyncClient, ASGITransport
        from api.main import app
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_health(self, client):
        async with client as c:
            resp = await c.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
