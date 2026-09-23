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
            value = market.get("expiration_time") or market.get("close_time") or "9999-12-31T23:59:59+00:00"
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return datetime.max.replace(tzinfo=timezone.utc)

        return sorted((market for market in markets if isinstance(market, dict)), key=expiration)

    def get_order_book(self, ticker: str) -> dict[str, Any]:
        """Fetch the raw order book for a contract ticker."""

        if not ticker:
            raise ValueError("ticker must not be empty")
        response = self.client.request("GET", f"/markets/{ticker}/orderbook")
        return response.get("orderbook", response)

    def get_current_active_ticker(self) -> str | None:
        """Return the nearest-expiring open contract, if one exists."""

        markets = self.get_active_btc15m_markets()
        return str(markets[0]["ticker"]) if markets and markets[0].get("ticker") else None
