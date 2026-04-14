from __future__ import annotations

import json
import os
from typing import Optional

import redis

from engine.order import Order, OrderStatus, OrderType, Side, Trade


class RedisStateManager:
    """
    Persists order book state to Redis.

    Data layout:
        order:{order_id}    → Hash   (order fields)
        book:bids           → Sorted Set (score=price, member=order_id)
        book:asks           → Sorted Set (score=price, member=order_id)
        trades              → List   (JSON-encoded trade objects)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        client: Optional[redis.Redis] = None,
    ) -> None:
        """
        Connect to Redis. Pass an existing client for testing,
        or let the manager create its own connection.
        """
        if client:
            self._r = client
        elif (url := os.getenv("REDIS_URL")):
            self._r = redis.Redis.from_url(url, decode_responses=True)
        else:
            self._r = redis.Redis(host=host, port=port, db=db, decode_responses=True)

        self.KEY_BIDS = "book:bids"
        self.KEY_ASKS = "book:asks"
        self.KEY_TRADES = "trades"

    def flush(self) -> None:
        """Delete all order book keys. Used for testing and resets."""
        for key in self._r.scan_iter("order:*"):
            self._r.delete(key)
        self._r.delete(self.KEY_BIDS, self.KEY_ASKS, self.KEY_TRADES)

    def save_order(self, order: Order) -> None:
        """
        Persist a new order to Redis.

        Creates a hash with all order fields and adds the order ID
        to the appropriate sorted set (bids or asks) scored by price.
        """
        order_key = f"order:{order.order_id}"

        self._r.hset(order_key, mapping={
            "order_id": order.order_id,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "price": str(order.price) if order.price is not None else "",
            "quantity": str(order.quantity),
            "remaining": str(order.remaining),
            "status": order.status.value,
            "timestamp": str(order.timestamp),
        })

        if order.side == Side.BUY:
            self._r.zadd(self.KEY_BIDS, {order.order_id: order.price})
        else:
            self._r.zadd(self.KEY_ASKS, {order.order_id: order.price})

    def update_order(self, order: Order) -> None:
        """
        Update an existing order's mutable fields after a fill or cancel.

        If the order is fully filled or cancelled, removes it from
        the sorted set so it no longer appears in price-level queries.
        """
        order_key = f"order:{order.order_id}"

        self._r.hset(order_key, mapping={
            "remaining": str(order.remaining),
            "status": order.status.value,
        })

        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
            if order.side == Side.BUY:
                self._r.zrem(self.KEY_BIDS, order.order_id)
            else:
                self._r.zrem(self.KEY_ASKS, order.order_id)

    def save_trade(self, trade: Trade) -> None:
        """
        Append a trade to the trade log.

        Trades are immutable after creation, so we serialize the
        entire object as a JSON blob and push it onto a list.
        """
        trade_data = json.dumps({
            "trade_id": trade.trade_id,
            "buy_order_id": trade.buy_order_id,
            "sell_order_id": trade.sell_order_id,
            "price": trade.price,
            "quantity": trade.quantity,
            "timestamp": trade.timestamp,
        })

        self._r.rpush(self.KEY_TRADES, trade_data)

    def get_snapshot(self, recent_trade_count: int = 20) -> dict:
        """
        Build a full order book snapshot from Redis alone.

        Reads the sorted sets for bid/ask levels, aggregates by price,
        and pulls recent trades from the trade log list.
        """
        bid_levels = self._aggregate_side(self.KEY_BIDS, descending=True)
        ask_levels = self._aggregate_side(self.KEY_ASKS, descending=False)

        if bid_levels:
            bb_price = bid_levels[0]["price"]
        else:
            bb_price = None

        if ask_levels:
            ba_price = ask_levels[0]["price"]
        else:            
            ba_price = None

        if bb_price and ba_price:
            spread = round(ba_price - bb_price, 10)
        else:
            spread = None

        trade_count = self._r.llen(self.KEY_TRADES)
        raw_trades = self._r.lrange(self.KEY_TRADES, -recent_trade_count, -1)
        recent_trades = []
        for i in raw_trades:
            try:
                recent_trades.append(json.loads(i))
            except json.JSONDecodeError:
                continue
        
        bid_order_count = 0
        ask_order_count = 0

        for lvl in bid_levels:
            bid_order_count += lvl["order_count"]
        for lvl in ask_levels:
            ask_order_count += lvl["order_count"]

        return {
            "bids": bid_levels,
            "asks": ask_levels,
            "spread": spread,
            "bid_count": bid_order_count,
            "ask_count": ask_order_count,
            "total_trades": trade_count,
            "recent_trades": recent_trades,
        }

    def recover_orders(self) -> list[Order]:
        """
        Reconstruct Order objects from Redis hashes on startup.

        Scans for all order:* keys, reads each hash, and rebuilds
        Order instances. Only returns orders that are still live
        (open or partial) — filled/cancelled orders are skipped.
        """
        orders = []

        for key in self._r.scan_iter("order:*"):
            data = self._r.hgetall(key)
            if not data:
                continue

            status = data["status"]
            if status in ("filled", "cancelled"):
                continue

            price = float(data["price"]) if data["price"] else None

            order = Order(
                side=Side(data["side"]),
                order_type=OrderType(data["order_type"]),
                price=price,
                quantity=float(data["quantity"]),
                order_id=data["order_id"],
            )

            order.timestamp = float(data["timestamp"])

            filled_qty = float(data["quantity"]) - float(data["remaining"])
            if filled_qty > 0:
                order.fill(filled_qty)

            orders.append(order)

        return orders

    def _aggregate_side(self, key: str, descending: bool) -> list[dict]:
        """
        Read a sorted set and aggregate orders by price level.

        For each order ID in the set, looks up its remaining quantity
        from the order hash and groups by price.
        """
        if descending:
            members = self._r.zrevrangebyscore(key, "+inf", "-inf", withscores=True)
        else:
            members = self._r.zrangebyscore(key, "-inf", "+inf", withscores=True)

        levels: dict[float, dict] = {}

        for order_id, price in members:
            remaining = self._r.hget(f"order:{order_id}", "remaining")
            if remaining is None:
                continue

            remaining = float(remaining)
            if remaining <= 0:
                continue

            if price not in levels:
                levels[price] = {
                    "price": price,
                    "total_quantity": 0.0,
                    "order_count": 0,
                }
            levels[price]["total_quantity"] += remaining
            levels[price]["order_count"] += 1

        return list(levels.values())
