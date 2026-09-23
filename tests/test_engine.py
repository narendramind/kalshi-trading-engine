"""Offline tests for the engine's contracts and risk-sensitive behavior."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from config import Settings
from core.client import KalshiClient
from core.execution import ExecutionEngine
from core.market import MarketResolver
from core.risk import RiskManager
from strategies.example_strategy import SimpleSpreadStrategy


class EngineTests(unittest.TestCase):
    def test_settings_select_production_url(self) -> None:
        settings = Settings(KALSHI_ENV="prod")
        self.assertEqual(settings.base_url, "https://api.elections.kalshi.com/trade-api/v2")

    def test_market_sort_uses_expiration_time(self) -> None:
        client = Mock()
        client.request.return_value = {
            "markets": [
                {"ticker": "later", "expiration_time": "2026-01-01T00:10:00Z", "close_time": "2026-01-01T00:01:00Z"},
                {"ticker": "soon", "expiration_time": "2026-01-01T00:05:00Z", "close_time": "2026-01-01T00:04:00Z"},
            ]
        }
        markets = MarketResolver(client).get_active_btc15m_markets()
        self.assertEqual([market["ticker"] for market in markets], ["soon", "later"])

    def test_strategy_adapts_dict_order_book_levels(self) -> None:
        signal = SimpleSpreadStrategy(spread_threshold_cents=5).on_tick(
            {"orderbook": {"yes": [{"yes_price": 40}], "no": [{"no_price": 55}]}}
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal["price"], 41)

    def test_dry_run_order_does_not_call_client(self) -> None:
        client = Mock()
        result = ExecutionEngine(client, dry_run=True).place_order("KXBTC15M-test", "buy", "yes", 1, 41)
        self.assertTrue(result["dry_run"])
        client.request.assert_not_called()

    def test_risk_manager_halts_at_daily_loss_limit(self) -> None:
        settings = Settings(MAX_DAILY_LOSS_USD=100, MAX_POSITION_SIZE=10)
        execution = Mock()
        manager = RiskManager(settings, execution)
        manager.update_daily_pnl(-100)
        self.assertTrue(manager.trading_halted)
        self.assertFalse(manager.check_order_allowed("ticker", 1, []))

    def test_client_uses_injected_clock_and_private_key(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        session = Mock()
        session.request.return_value = Mock(ok=True, status_code=200, content=b"{}", json=lambda: {})
        client = KalshiClient(
            Settings(KALSHI_KEY_ID="key"),
            session=session,
            private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
            clock=lambda: 123.456,
        )
        client.request("GET", "markets")
        headers = session.request.call_args.kwargs["headers"]
        self.assertEqual(headers["KALSHI-ACCESS-TIMESTAMP"], "123456")


if __name__ == "__main__":
    unittest.main()