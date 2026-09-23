"""Market discovery and order-book access."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.client import KalshiClient


class MarketResolver:
    """Resolve currently tradeable KXBTC15M contracts."""

    SERIES_TICKER = "KXBTC15M"

    def __init__(self, client: KalshiClient) -> None:
        self.client = client

    def get_active_btc15m_markets(self) -> list[dict[str, Any]]:
        """Return open series markets ordered by soonest expiration."""

        response = self.client.request(
            "GET", "/markets", params={"series_ticker": self.SERIES_TICKER, "status": "open", "limit": 100}
        )
        markets = response.get("markets", [])

        def expiration(market: dict[str, Any]) -> datetime:
            value = (
                market.get("expected_expiration_time")
                or market.get("occurrence_datetime")
                or market.get("expiration_time")
                or market.get("close_time")
                or "9999-12-31T23:59:59+00:00"
            )
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return datetime.max.replace(tzinfo=timezone.utc)

        active_statuses = {"active", "open"}
        active_markets = (
            market
            for market in markets
            if isinstance(market, dict) and str(market.get("status", "open")).lower() in active_statuses
        )
        return sorted(active_markets, key=expiration)

    def get_order_book(self, ticker: str) -> dict[str, Any]:
        """Fetch and normalize an order book to integer-cent ``yes``/``no`` levels."""

        if not ticker:
            raise ValueError("ticker must not be empty")
        response = self.client.request("GET", f"/markets/{ticker}/orderbook")
        book = response.get("orderbook_fp", response.get("orderbook", response))
        if not isinstance(book, dict):
            raise ValueError("Kalshi order-book response did not contain an object")
        return {
            "yes": self._normalize_levels(book.get("yes", book.get("yes_dollars", [])), dollars="yes_dollars" in book),
            "no": self._normalize_levels(book.get("no", book.get("no_dollars", [])), dollars="no_dollars" in book),
        }

    @staticmethod
    def _normalize_levels(levels: Any, dollars: bool) -> list[list[int]]:
        """Convert Kalshi fixed-point levels to the strategy's cent contract."""

        normalized: list[list[int]] = []
        for level in levels if isinstance(levels, list) else []:
            if not isinstance(level, (list, tuple)) or len(level) < 2:
                continue
            try:
                price = round(float(level[0]) * 100) if dollars else int(level[0])
                normalized.append([price, int(float(level[1]))])
            except (TypeError, ValueError):
                continue
        return normalized

    def get_current_active_ticker(self) -> str | None:
        """Return the nearest-expiring open contract, if one exists."""

        markets = self.get_active_btc15m_markets()
        return str(markets[0]["ticker"]) if markets and markets[0].get("ticker") else None
