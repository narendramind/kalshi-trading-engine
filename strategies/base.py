"""Interfaces shared by trading strategies."""

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):
    """Abstract strategy contract for market ticks and position exits."""

    @abstractmethod
    def on_tick(self, market_data: dict[str, Any]) -> dict[str, Any] | None:
        """Evaluate a market snapshot and optionally return a trade signal."""

    @abstractmethod
    def should_exit(self, position: dict[str, Any]) -> bool:
        """Return whether an existing position should be closed."""
