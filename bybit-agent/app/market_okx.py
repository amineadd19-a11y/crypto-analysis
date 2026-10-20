"""OKX public market helpers (legitimate public API fallback)."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from app.market_data_core import DEFAULT_TIMEOUT_SEC, UpstreamMarketError, _http_get_json

OKX_HOST = "https://www.okx.com"
_OKX_BAR = {"1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m", "60": "1H", "120": "2H", "240": "4H", "360": "6H", "720": "12H", "D": "1D", "W": "1W", "M": "1M"}


def _to_okx_inst(symbol: str) -> str:
    s = symbol.upper().strip()
    if s.endswith("-USDT-SWAP"):
        return s
    if s.endswith("USDT") and len(s) > 4:
        return f"{s[:-4]}-USDT-SWAP"
    raise UpstreamMarketError(f"Cannot map symbol {symbol!r} to OKX USDT-SWAP.", kind="bybit_ret")


def _from_okx_inst(inst_id: str) -> str:
    parts = inst_id.upper().split("-")
    if len(parts) >= 2 and parts[1] == "USDT":
        return f"{parts[0]}USDT"
    return inst_id.replace("-", "")


def okx_get_tickers(category: str = "linear", symbol: str | None = None, timeout: float = DEFAULT_TIMEOUT_SEC) -> dict:
    if category not in ("linear", "spot"):
        raise UpstreamMarketError("OKX fallback supports linear or spot only.", kind="bybit_ret")
    if symbol:
        if category == "spot":
            base = symbol.upper()
            inst = f"{base[:-4]}-USDT" if base.endswith("USDT") else base
        else:
            inst = _to_okx_inst(symbol)
        path, params = "/api/v5/market/ticker", {"instId": inst}
    elif category == "spot":
        path, params = "/api/v5/market/tickers", {"instType": "SPOT"}
    else:
        path, params = "/api/v5/market/tickers", {"instType": "SWAP"}
    payload, host = _http_get_json(f"{OKX_HOST}{path}?{urlencode(params)}", timeout=timeout)
    if str(payload.get("code", "0")) not in ("0",):
        raise UpstreamMarketError(f"OKX market rejected: {payload.get('msg', '')}"[:160], host=host, kind="bybit_ret")
    rows = payload.get("data") or []
    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        inst = str(item.get("instId", ""))
        if category == "linear" and not inst.endswith("-USDT-SWAP"):
            continue
        try:
            last = float(item.get("last") or 0)
            open24 = item.get("open24h") or item.get("sodUtc0") or item.get("last")
            open24f = float(open24) if open24 not in (None, "") else last
            change_pct = ((last - open24f) / open24f) if open24f else 0.0
            vol24 = float(item.get("volCcy24h") or item.get("vol24h") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0:
            continue
        normalized.append({"symbol": _from_okx_inst(inst), "lastPrice": str(last), "price24hPcnt": str(change_pct), "turnover24h": str(vol24), "okx_instId": inst})
    return {"retCode": 0, "result": {"list": normalized, "category": category}, "_resolved_host": host, "_data_source": "okx-public"}


def okx_get_kline(symbol: str, interval: str, limit: int, timeout: float = DEFAULT_TIMEOUT_SEC) -> dict:
    bar = _OKX_BAR.get(interval)
    if not bar:
        raise UpstreamMarketError(f"Unsupported interval for OKX fallback: {interval}", kind="bybit_ret")
    inst = _to_okx_inst(symbol)
    lim = min(max(limit, 1), 300)
    params = {"instId": inst, "bar": bar, "limit": str(lim)}
    payload, host = _http_get_json(f"{OKX_HOST}/api/v5/market/candles?{urlencode(params)}", timeout=timeout)
    if str(payload.get("code", "0")) not in ("0",):
        raise UpstreamMarketError(f"OKX kline rejected: {payload.get('msg', '')}"[:160], host=host, kind="bybit_ret")
    candles = []
    for row in payload.get("data") or []:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        candles.append([str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4])])
    return {"retCode": 0, "result": {"list": candles, "symbol": symbol, "category": "linear"}, "_resolved_host": host, "_data_source": "okx-public"}
