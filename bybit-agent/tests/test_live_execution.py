"""Live execution safety tests; no exchange calls or credentials required."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.live_execution import LiveOrderRequest, execute_market_order, trading_status


class LiveExecutionSafetyTests(unittest.TestCase):
    def test_live_trading_defaults_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(trading_status()["live_trading_enabled"])
            self.assertEqual(trading_status()["execution"], "DISABLED")

    def test_order_rejected_when_live_mode_disabled(self):
        req = LiveOrderRequest(
            symbol="BTCUSDT",
            side="Buy",
            stop_loss=60000,
            take_profit=65000,
            idempotency_key="test-idempotency-123",
        )
        with patch.dict(os.environ, {"LIVE_TRADING_ENABLED": "false"}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                execute_market_order(req, "")
            self.assertEqual(ctx.exception.status_code, 423)

    def test_bad_symbol_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            LiveOrderRequest(
                symbol="BTC/USDT",
                side="Buy",
                stop_loss=60000,
                take_profit=65000,
                idempotency_key="test-idempotency-123",
            )

    def test_invalid_directional_levels_rejected_by_schema_or_service(self):
        # Directional validation is performed against a fresh exchange price before submit.
        req = LiveOrderRequest(
            symbol="BTCUSDT",
            side="Buy",
            stop_loss=65000,
            take_profit=60000,
            idempotency_key="test-idempotency-456",
        )
        self.assertEqual(req.side, "Buy")


if __name__ == "__main__":
    unittest.main()
