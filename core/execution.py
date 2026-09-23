"""Order submission and portfolio operations."""

from __future__ import annotations

import logging
from typing import Any, Literal

from core.client import KalshiClient

LOGGER = logging.getLogger(__name__)
Action = Literal["buy", "sell"]
Side = Literal["yes", "no"]


class ExecutionEngine:
    """Submit orders to Kalshi or simulate them without network side effects."""

    def __init__(self, client: KalshiClient, dry_run: bool = True) -> None:
        self.client = client
        self.dry_run = dry_run

    @staticmethod
    def _build_order_payload(ticker: str, action: Action, side: Side, count: int, price: int) -> dict[str, Any]:
        if action not in ("buy", "sell") or side not in ("yes", "no"):
            raise ValueError("action must be buy/sell and side must be yes/no")
        if not ticker or count <= 0 or not 1 <= price <= 99:
            raise ValueError("ticker, count, and a price from 1 through 99 are required")
        payload: dict[str, Any] = {"ticker": ticker, "action": action, "side": side, "count": count, "type": "limit"}
        payload[f"{side}_price"] = price
        return payload

    def place_order(self, ticker: str, action: Action, side: Side, count: int, price: int) -> dict[str, Any]:
        """Place a limit order using Kalshi cent prices."""

        payload = self._build_order_payload(ticker, action, side, count, price)
        if self.dry_run:
            result = {"dry_run": True, "order": payload}
            LOGGER.info("DRY RUN order: %s", payload)
            return result
        return self.client.request("POST", "/portfolio/orders", json=payload)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel one order by ID."""

        if not order_id:
            raise ValueError("order_id must not be empty")
        if self.dry_run:
            LOGGER.info("DRY RUN cancel order: %s", order_id)
            return {"dry_run": True, "order_id": order_id, "cancelled": True}
        return self.client.request("DELETE", f"/portfolio/orders/{order_id}")

    def get_open_positions(self) -> list[dict[str, Any]]:
        """Return current portfolio positions."""

        if self.dry_run:
            return []
        response = self.client.request("GET", "/portfolio/positions")
        return response.get("market_positions", response.get("positions", []))

    def cancel_all_open_orders(self) -> list[dict[str, Any]]:
        """Cancel all resting orders and return cancellation responses."""

        if self.dry_run:
            LOGGER.warning("DRY RUN emergency stop: no live orders cancelled")
            return []
        orders = self.client.request("GET", "/portfolio/orders", params={"status": "resting", "limit": 100}).get("orders", [])
        return [self.cancel_order(str(order["order_id"])) for order in orders if order.get("order_id")]
