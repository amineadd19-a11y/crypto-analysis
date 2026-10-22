"""Public market-data: Bybit primary, OKX public fallback. Never fabricates prices."""
from __future__ import annotations

import time
from typing import Any

from app.market_data_core import UpstreamMarketError, bybit_market_get, raise_as_http
from app.market_okx import okx_get_kline, okx_get_tickers

__all__ = ["UpstreamMarketError", "bybit_market_get", "get_tickers", "get_kline", "probe_market_connectivity", "get_instruments", "raise_as_http"]


def get_tickers(category: str = "linear", symbol: str | None = None) -> dict:
    try:
        params: dict[str, Any] = {"category": category}
        if symbol:
            params["symbol"] = symbol
        return bybit_market_get("/v5/market/tickers", params)
    except UpstreamMarketError as bybit_err:
        try:
            out = okx_get_tickers(category=category, symbol=symbol)
            out["_bybit_error"] = bybit_err.kind
            return out
        except UpstreamMarketError:
            raise bybit_err



def get_instruments(category: str = "linear") -> dict:
    """Return the active contract universe; fall back transparently to OKX public swaps."""
    if category not in ("linear", "spot"):
        raise UpstreamMarketError("Unsupported instrument category.", kind="bybit_ret")
    try:
        params: dict[str, Any] = {"category": category, "limit": 1000}
        rows: list[dict[str, Any]] = []
        cursor = None
        seen_cursors: set[str] = set()
        while True:
            page_params = dict(params)
            if cursor:
                page_params["cursor"] = cursor
            page = bybit_market_get("/v5/market/instruments-info", page_params)
            result = page.get("result") or {}
            rows.extend(x for x in (result.get("list") or []) if isinstance(x, dict))
            next_cursor = str(result.get("nextPageCursor") or "")
            if not next_cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        if category == "linear":
            rows = [
                row for row in rows
                if row.get("quoteCoin") == "USDT"
                and row.get("contractType") == "LinearPerpetual"
                and row.get("status") == "Trading"
            ]
        else:
            rows = [row for row in rows if row.get("status") == "Trading"]
        return {
            "category": category, "result": {"list": rows},
            "_data_source": "bybit", "_resolved_host": page.get("_resolved_host"),
            "_bybit_error": None, "_universe_complete": True,
        }
    except UpstreamMarketError as bybit_err:
        # Do not label this as the Bybit universe: OKX lists only its own instruments.
        fallback = okx_get_tickers(category=category)
        fallback_rows = fallback.get("result", {}).get("list", []) or []
        fallback["_bybit_error"] = bybit_err.kind
        fallback["_universe_complete"] = False
        fallback["_universe_note"] = "Bybit instrument endpoint unavailable; this is the OKX public instrument universe, not the full Bybit universe."
        fallback["result"]["list"] = fallback_rows
        return fallback

def get_kline(category: str, symbol: str, interval: str, limit: int) -> dict:
    try:
        return bybit_market_get("/v5/market/kline", {"category": category, "symbol": symbol, "interval": interval, "limit": limit})
    except UpstreamMarketError as bybit_err:
        try:
            out = okx_get_kline(symbol=symbol, interval=interval, limit=limit)
            out["_bybit_error"] = bybit_err.kind
            return out
        except UpstreamMarketError:
            raise bybit_err


def probe_market_connectivity(timeout: float = 5.0) -> dict:
    started = time.monotonic()
    bybit: dict[str, Any] = {"status": "unknown"}
    okx: dict[str, Any] = {"status": "unknown"}
    try:
        payload = bybit_market_get("/v5/market/tickers", {"category": "linear", "symbol": "BTCUSDT"}, timeout=timeout)
        row = (payload.get("result") or {}).get("list") or []
        bybit = {"status": "ok", "host": payload.get("_resolved_host"), "sample_last_price_present": bool(row and row[0].get("lastPrice"))}
    except UpstreamMarketError as exc:
        bybit = {"status": "degraded", "kind": exc.kind, "http_status": exc.status, "host": exc.host, "message": exc.message}
    try:
        op = okx_get_tickers(category="linear", symbol="BTCUSDT", timeout=timeout)
        row = (op.get("result") or {}).get("list") or []
        okx = {"status": "ok", "host": op.get("_resolved_host"), "sample_last_price_present": bool(row and row[0].get("lastPrice"))}
    except UpstreamMarketError as exc:
        okx = {"status": "degraded", "kind": exc.kind, "http_status": exc.status, "host": exc.host, "message": exc.message}
    active = "bybit" if bybit.get("status") == "ok" else ("okx-public" if okx.get("status") == "ok" else "none")
    return {
        "status": "ok" if active != "none" else "degraded",
        "active_source": active,
        "bybit": bybit,
        "okx_public": okx,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "note": "Analysis uses Bybit when reachable; otherwise OKX public USDT-SWAP. OAuth remains Bybit-only on api2.",
    }
