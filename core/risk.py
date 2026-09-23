"""Trading risk controls and emergency shutdown behavior."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from config import Settings

if TYPE_CHECKING:
    from core.execution import ExecutionEngine

LOGGER = logging.getLogger(__name__)


class RiskManager:
    """Enforce position and daily-loss limits for a single process."""

    def __init__(self, settings: Settings, execution: ExecutionEngine) -> None:
        self.max_daily_loss_usd = settings.max_daily_loss_usd
        self.max_position_size = settings.max_position_size
        self.execution = execution
        self.daily_pnl_usd = 0.0
        self.trading_halted = False

    @staticmethod
    def _position_size(position: dict[str, Any]) -> int:
        """Normalize common Kalshi position field names to contract count."""

        raw_value = position.get("position")
        if raw_value is None:
            raw_value = position.get("position_fp", position.get("count", 0))
        try:
            return abs(int(float(raw_value or 0)))
        except (TypeError, ValueError):
            LOGGER.warning("Ignoring malformed position payload: %s", position)
            return 0

    def check_order_allowed(self, ticker: str, count: int, positions: list[dict[str, Any]] | None = None) -> bool:
        """Return whether adding ``count`` contracts stays within the ticker limit."""

        if self.trading_halted or count <= 0:
            return False
        current = 0
        for position in positions if positions is not None else self.execution.get_open_positions():
            if position.get("ticker") == ticker:
                current += self._position_size(position)
        allowed = current + count <= self.max_position_size
        if not allowed:
            LOGGER.warning("Order rejected by position limit: %s + %s > %s", current, count, self.max_position_size)
        return allowed

    def update_daily_pnl(self, pnl_usd: float) -> None:
        """Update cumulative PnL and halt new trading after the loss threshold."""

        self.daily_pnl_usd += pnl_usd
        if self.daily_pnl_usd <= -self.max_daily_loss_usd:
            self.trading_halted = True
            LOGGER.error("Daily loss limit reached: %.2f USD", self.daily_pnl_usd)

    def emergency_stop(self) -> None:
        """Halt trading and cancel all resting orders."""

        self.trading_halted = True
        self.execution.cancel_all_open_orders()
        LOGGER.critical("Emergency stop engaged")
