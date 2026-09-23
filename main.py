"""Polling entry point for the Kalshi KXBTC15M example engine."""

from __future__ import annotations

import asyncio
import logging

from config import get_settings
from core.client import KalshiClient
from core.execution import ExecutionEngine
from core.market import MarketResolver
from core.risk import RiskManager
from strategies.base import BaseStrategy
from strategies.example_strategy import SimpleSpreadStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


async def poll_once(resolver: MarketResolver, execution: ExecutionEngine, risk: RiskManager, strategy: BaseStrategy) -> None:
    """Run one market discovery, strategy, risk, and execution cycle."""

    ticker = await asyncio.to_thread(resolver.get_current_active_ticker)
    if not ticker:
        LOGGER.info("No active %s market found", resolver.SERIES_TICKER)
        return
    order_book = await asyncio.to_thread(resolver.get_order_book, ticker)
    signal = strategy.on_tick({"ticker": ticker, "orderbook": order_book})
    if signal and risk.check_order_allowed(ticker, int(signal["count"])):
        LOGGER.info("Strategy signal for %s: %s", ticker, signal)
        await asyncio.to_thread(execution.place_order, ticker, signal["action"], signal["side"], signal["count"], signal["price"])


async def run() -> None:
    """Construct dependencies and run until interrupted."""

    settings = get_settings()
    client = KalshiClient(settings)
    resolver = MarketResolver(client)
    execution = ExecutionEngine(client, dry_run=True)
    risk = RiskManager(settings, execution)
    strategy = SimpleSpreadStrategy()
    try:
        while not risk.trading_halted:
            try:
                await poll_once(resolver, execution, risk, strategy)
            except Exception:
                LOGGER.exception("Polling cycle failed; continuing after delay")
            await asyncio.sleep(10)
    finally:
        risk.emergency_stop()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested")
