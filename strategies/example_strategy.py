"""A deliberately simple spread-based example strategy."""

from __future__ import annotations

from typing import Any

from strategies.base import BaseStrategy


class SimpleSpreadStrategy(BaseStrategy):
    """Emit a small buy signal when the best yes spread is wide enough."""

    def __init__(self, spread_threshold_cents: int = 5, order_count: int = 1) -> None:
        if spread_threshold_cents <= 0 or order_count <= 0:
            raise ValueError("spread_threshold_cents and order_count must be positive")
        self.spread_threshold_cents = spread_threshold_cents
        self.order_count = order_count
        self.last_best_bid: int | None = None
        self.last_best_ask: int | None = None
        self.last_spread_cents: int | None = None

    @staticmethod
    def _price(level: Any, side: str) -> int | None:
        if isinstance(level, (list, tuple)) and level:
            return int(level[0])
        if isinstance(level, dict):
            value = level.get("price")
            if value is None:
                value = level.get(f"{side}_price")
            return int(value) if value is not None else None
        return None

    def on_tick(self, market_data: dict[str, Any]) -> dict[str, Any] | None:
        """Return a signal when the best bid/ask spread exceeds the threshold."""

        book = market_data.get("orderbook", market_data)
        bids = book.get("yes", book.get("bids", []))
        asks = book.get("no", book.get("asks", []))
        best_bid = max((price for price in (self._price(level, "yes") for level in bids) if price is not None), default=None)
        best_no_ask = max((price for price in (self._price(level, "no") for level in asks) if price is not None), default=None)
        best_ask = 100 - best_no_ask if best_no_ask is not None else None
        self.last_best_bid = best_bid
        self.last_best_ask = best_ask
        self.last_spread_cents = best_ask - best_bid if best_bid is not None and best_ask is not None else None
        if self.last_spread_cents is None or self.last_spread_cents < self.spread_threshold_cents:
            return None
        return {
            "action": "buy",
            "side": "yes",
            "count": self.order_count,
            "price": best_bid + 1,
            "reason": f"spread={self.last_spread_cents}c",
        }

    def should_exit(self, position: dict[str, Any]) -> bool:
        """This example has no position-specific exit rule."""

        return False

    def get_tick_diagnostics(self) -> dict[str, Any]:
        """Return the latest spread inputs for operator-facing logs."""

        return {
            "best_bid_cents": self.last_best_bid,
            "best_ask_cents": self.last_best_ask,
            "spread_cents": self.last_spread_cents,
            "threshold_cents": self.spread_threshold_cents,
        }
