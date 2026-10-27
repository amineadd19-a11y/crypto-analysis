"""Fail-closed Bybit USDT perpetual live execution.

Live trading is opt-in and requires server-side credentials plus a separate confirmation secret.
Never returns credentials. Market orders carry exchange-side stop loss and take profit.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from pybit.unified_trading import HTTP


class LiveOrderRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{3,30}$")
    side: Literal["Buy", "Sell"]
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    idempotency_key: str = Field(min_length=12, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


def _enabled() -> bool:
    return os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"


def _client() -> HTTP:
    key = os.getenv("BYBIT_API_KEY", "").strip()
    secret = os.getenv("BYBIT_API_SECRET", "").strip()
    if not key or not secret:
        raise HTTPException(status_code=503, detail="Live execution is not configured: add dedicated Bybit AI-subaccount API credentials as server-side environment variables.")
    return HTTP(
        testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true",
        api_key=key,
        api_secret=secret,
        timeout=10,
        force_retry=False,
        max_retries=1,
        retry_delay=0,
    )


def _result(response: dict, operation: str) -> dict:
    if not isinstance(response, dict) or response.get("retCode") != 0:
        # Do not expose request payloads, keys, signatures, or upstream internals.
        raise HTTPException(status_code=502, detail=f"Bybit rejected {operation}; no success was confirmed.")
    return response.get("result") or {}


def trading_status() -> dict:
    configured = bool(os.getenv("BYBIT_API_KEY", "").strip() and os.getenv("BYBIT_API_SECRET", "").strip())
    confirmation_set = bool(os.getenv("LIVE_TRADING_CONFIRMATION", "").strip())
    return {
        "execution": "LIVE" if _enabled() and configured and confirmation_set else "DISABLED",
        "live_trading_enabled": _enabled(),
        "credentials_configured": configured,
        "confirmation_secret_configured": confirmation_set,
        "environment": "testnet" if os.getenv("BYBIT_TESTNET", "false").lower() == "true" else "mainnet",
        "withdrawals_supported": False,
        "automatic_monitoring": False,
        "note": "Vercel functions are request-driven; continuous autonomous monitoring requires a durable worker/scheduler.",
    }


def _check_daily_loss(client: HTTP, daily_loss_limit: float) -> float:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = _result(client.get_closed_pnl(
        category="linear",
        startTime=int(start.timestamp() * 1000),
        endTime=int(now.timestamp() * 1000),
        limit=100,
    ), "daily realized-PnL check")
    # Do not trade if pagination means we cannot verify the full day's losses.
    if result.get("nextPageCursor"):
        raise HTTPException(status_code=503, detail="Daily closed-PnL history exceeds one page; trading paused until complete daily-loss pagination is implemented.")
    rows = result.get("list") or []
    total = 0.0
    for row in rows:
        try:
            pnl = float(row.get("closedPnl", 0) or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=503, detail="Daily PnL data is malformed; trading paused.")
        if not math.isfinite(pnl):
            raise HTTPException(status_code=503, detail="Daily PnL data is invalid; trading paused.")
        total += pnl
    if total <= -daily_loss_limit:
        raise HTTPException(status_code=409, detail="Daily realized-loss limit reached; no new trades allowed.")
    return total


def execute_market_order(body: LiveOrderRequest, confirmation: str) -> dict:
    if not _enabled():
        raise HTTPException(status_code=423, detail="Live trading is disabled. Set LIVE_TRADING_ENABLED=true only after completing the deployment safety checklist.")
    expected = os.getenv("LIVE_TRADING_CONFIRMATION", "").strip()
    if not expected or not confirmation or not __import__("hmac").compare_digest(expected, confirmation):
        raise HTTPException(status_code=403, detail="Live-trade confirmation failed.")
    client = _client()
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    if not testnet and os.getenv("LIVE_MAINNET_ACK", "").strip() != "I_UNDERSTAND_REAL_FUNDS":
        raise HTTPException(status_code=423, detail="Mainnet execution is not armed. Complete explicit mainnet acknowledgement in deployment settings.")

    symbol = body.symbol.upper()
    stop = float(body.stop_loss)
    target = float(body.take_profit)
    # Fetch a fresh market price and exchange constraints; never accept a client-provided entry.
    ticker_result = _result(client.get_tickers(category="linear", symbol=symbol), "ticker lookup")
    tickers = ticker_result.get("list") or []
    if len(tickers) != 1:
        raise HTTPException(status_code=404, detail="Symbol is not available as a linear perpetual on Bybit.")
    try:
        price = float(tickers[0]["lastPrice"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail="Bybit returned an invalid market price.")
    if not math.isfinite(price) or price <= 0:
        raise HTTPException(status_code=503, detail="Bybit market price is invalid.")

    if body.side == "Buy" and not (stop < price < target):
        raise HTTPException(status_code=422, detail="For Buy, stop_loss must be below the current price and take_profit above it.")
    if body.side == "Sell" and not (target < price < stop):
        raise HTTPException(status_code=422, detail="For Sell, take_profit must be below the current price and stop_loss above it.")
    if abs(price - stop) / price > 0.03:
        raise HTTPException(status_code=422, detail="Stop distance exceeds the 3% safety ceiling; no order submitted.")

    # Verify full daily PnL before opening any new exposure.
    daily_limit = float(os.getenv("MAX_DAILY_LOSS_USDT", "5"))
    if not math.isfinite(daily_limit) or daily_limit <= 0:
        raise HTTPException(status_code=503, detail="MAX_DAILY_LOSS_USDT must be a positive finite amount.")
    daily_pnl = _check_daily_loss(client, daily_limit)

    wallet = _result(client.get_wallet_balance(accountType="UNIFIED"), "wallet/equity lookup")
    accounts = wallet.get("list") or []
    try:
        equity = float(accounts[0]["totalEquity"]) if accounts else 0.0
    except (KeyError, TypeError, ValueError):
        equity = 0.0
    if not math.isfinite(equity) or equity <= 0:
        raise HTTPException(status_code=503, detail="Unable to verify positive unified-account equity.")

    # Avoid stacking/reversing positions: only one open position per symbol is permitted.
    positions = _result(client.get_positions(category="linear", symbol=symbol), "open-position check").get("list") or []
    for pos in positions:
        try:
            if float(pos.get("size", 0) or 0) > 0:
                raise HTTPException(status_code=409, detail="An open position already exists for this symbol; no additional order submitted.")
        except (TypeError, ValueError):
            raise HTTPException(status_code=503, detail="Position data is malformed; trading paused.")

    instruments = _result(client.get_instruments_info(category="linear", symbol=symbol), "instrument rules lookup").get("list") or []
    if len(instruments) != 1:
        raise HTTPException(status_code=404, detail="Instrument rules are unavailable.")
    lot = instruments[0].get("lotSizeFilter") or {}
    try:
        step = Decimal(str(lot["qtyStep"]))
        min_qty = Decimal(str(lot["minOrderQty"]))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail="Bybit quantity rules are invalid.")

    # Conservative risk: <=0.5% of equity per order, <=100% equity notional, no leverage increase.
    risk_pct = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "0.5"))
    if not math.isfinite(risk_pct) or not 0 < risk_pct <= 0.5:
        raise HTTPException(status_code=503, detail="MAX_RISK_PER_TRADE_PCT must be between 0 and 0.5.")
    risk_budget = min(equity * risk_pct / 100.0, max(0.0, daily_limit + daily_pnl))
    risk_distance = abs(price - stop)
    qty_raw = min(risk_budget / risk_distance, equity / price)
    qty = (Decimal(str(qty_raw)) / step).to_integral_value(rounding=ROUND_DOWN) * step
    if qty < min_qty or qty <= 0:
        raise HTTPException(status_code=422, detail="Safe position size is below Bybit minimum quantity; no order submitted.")
    qty_text = format(qty, "f").rstrip("0").rstrip(".") if "." in format(qty, "f") else format(qty, "f")
    client_order_id = "ai" + hashlib.sha256(body.idempotency_key.encode("utf-8")).hexdigest()[:32]

    # Exchange-side protection is attached to the entry request. Fail closed on any API error.
    order = _result(client.place_order(
        category="linear",
        symbol=symbol,
        side=body.side,
        orderType="Market",
        qty=qty_text,
        positionIdx=0,
        stopLoss=format(Decimal(str(stop)), "f"),
        takeProfit=format(Decimal(str(target)), "f"),
        tpslMode="Full",
        slTriggerBy="MarkPrice",
        tpTriggerBy="MarkPrice",
        orderLinkId=client_order_id,
    ), "market order")
    return {
        "submitted": True,
        "confirmed_by_exchange": True,
        "symbol": symbol,
        "side": body.side,
        "reference_price": price,
        "quantity": qty_text,
        "stop_loss": stop,
        "take_profit": target,
        "risk_budget_usdt": round(risk_budget, 6),
        "equity_usdt": round(equity, 4),
        "daily_realized_pnl_usdt": round(daily_pnl, 4),
        "daily_loss_limit_usdt": daily_limit,
        "environment": "testnet" if testnet else "mainnet",
        "order_id": order.get("orderId"),
        "order_link_id": order.get("orderLinkId") or client_order_id,
        "execution": "LIVE",
        "note": "Order accepted by Bybit; verify actual fill and protective orders in the exchange UI.",
    }
