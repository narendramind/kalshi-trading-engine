"""Authenticated Kalshi API v2 HTTP client."""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from config import Settings

LOGGER = logging.getLogger(__name__)


class HTTPSession(Protocol):
    """Minimal HTTP session contract used by the client."""

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send an HTTP request."""


class KalshiAPIError(RuntimeError):
    """Raised when Kalshi returns an unsuccessful API response."""

    def __init__(self, status_code: int, message: str, response_body: Any = None) -> None:
        super().__init__(f"Kalshi API error ({status_code}): {message}")
        self.status_code = status_code
        self.response_body = response_body


class KalshiClient:
    """Thread-safe-enough synchronous client intended for one trading process."""

    def __init__(
        self,
        settings: Settings,
        max_retries: int = 4,
        timeout_seconds: float = 10.0,
        *,
        session: HTTPSession | None = None,
        private_key: rsa.RSAPrivateKey | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.max_retries = max(0, max_retries)
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self._private_key = private_key or self._load_private_key()
        self._clock = clock
        self._sleep = sleeper

    def _load_private_key(self) -> rsa.RSAPrivateKey:
        if not self.settings.kalshi_key_id or not self.settings.kalshi_private_key_path:
            raise ValueError("KALSHI_KEY_ID and KALSHI_PRIVATE_KEY_PATH are required for API access")
        path = Path(self.settings.kalshi_private_key_path).expanduser()
        try:
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"Unable to load RSA private key from {path}") from exc
        if not isinstance(key, rsa.RSAPrivateKey):
            raise TypeError("Kalshi private key must be an RSA private key")
        return key

    def _headers(self, method: str, path: str) -> dict[str, str]:
        timestamp = str(int(self._clock() * 1000))
        message = f"{timestamp}{method.upper()}{path}".encode("utf-8")
        signature = self._private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.settings.kalshi_key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("ascii"),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Perform an authenticated request, retrying transient rate limits."""

        path = f"/{path.lstrip('/')}"
        url = f"{self.settings.base_url}{path}"
        request_kwargs = {"timeout": self.timeout_seconds, **kwargs}
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(method.upper(), url, headers=self._headers(method, path), **request_kwargs)
            except requests.RequestException as exc:
                raise KalshiAPIError(0, f"HTTP request failed: {exc}") from exc
            if response.status_code == 429 and attempt < self.max_retries:
                delay = min(30.0, 2**attempt)
                LOGGER.warning("Kalshi rate limit hit; retrying in %.1fs", delay)
                self._sleep(delay)
                continue
            try:
                body = response.json() if response.content else {}
            except ValueError:
                body = {"raw": response.text}
            if not response.ok:
                message = body.get("error", body.get("message", response.reason)) if isinstance(body, dict) else response.reason
                raise KalshiAPIError(response.status_code, str(message), body)
            if not isinstance(body, dict):
                raise KalshiAPIError(response.status_code, "Expected a JSON object", body)
            return body
        raise KalshiAPIError(429, "Rate limit retries exhausted")
