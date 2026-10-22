"""HTTP routes for multi-timeframe analysis. No order execution."""
from __future__ import annotations

from fastapi import HTTPException, Query

from app.market_data import UpstreamMarketError, get_kline, get_tickers, raise_as_http
from app.mtf_scanner import MTF_INTERVALS, analyze_symbol_mtf


def _load_symbol(symbol: str, limit: int) -> dict:
    candles_by_interval: dict[str, list] = {}
    sources: set[str] = set()
    warnings: list[str] = []
    for interval in MTF_INTERVALS:
        try:
            payload = get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        rows = (payload.get("result") or {}).get("list") or []
        if not rows:
            raise HTTPException(status_code=502, detail={"error": "empty_market_data", "symbol": symbol, "interval": interval})
        candles_by_interval[interval] = rows
        sources.add(str(payload.get("_data_source", "unknown")))
        if payload.get("_bybit_error"):
            warnings.append(f"{interval}: Bybit primary unavailable ({payload['_bybit_error']}); using fallback.")
    source = next(iter(sources)) if len(sources) == 1 else ("mixed" if sources else "unknown")
    result = analyze_symbol_mtf(symbol, candles_by_interval, data_source=source)
    result["market_data_warning"] = sorted(set(warnings))
    result["source_by_timeframe"] = {
        interval: source for interval, source in zip(MTF_INTERVALS, [str((getattr(payload, "_data_source", None) or source)) for payload in []])
    } if False else {label: source for label in result.get("timeframes", {})}
    result["execution"] = "DISABLED"
    result["trading_enabled"] = False
    return result


def register_mtf_routes(app) -> None:
    @app.get("/api/scan/mtf")
    def scan_mtf(
        symbol: str = Query(default="BTCUSDT", min_length=3, max_length=30, pattern="^[A-Za-z0-9_-]+$"),
        limit: int = Query(default=200, ge=60, le=300),
    ) -> dict:
        """Analyze one USDT perpetual on 1m/5m/15m/1h/4h."""
        normalized = symbol.upper()
        if not normalized.endswith("USDT"):
            raise HTTPException(status_code=400, detail="Only USDT-quoted perpetual symbols are supported.")
        return _load_symbol(normalized, limit)

    @app.get("/api/scan/smart")
    def scan_smart(
        top_n: int = Query(default=5, ge=1, le=10),
        limit: int = Query(default=200, ge=60, le=300),
        min_turnover: float = Query(default=5_000_000, gt=0),
    ) -> dict:
        """Rank liquid USDT perpetuals by multi-timeframe setup score."""
        try:
            payload = get_tickers(category="linear")
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        tickers = (payload.get("result") or {}).get("list") or []
        eligible = []
        for item in tickers:
            symbol = str(item.get("symbol", "")).upper()
            try:
                turnover = float(item.get("turnover24h") or 0)
                last_price = float(item.get("lastPrice") or 0)
            except (TypeError, ValueError):
                continue
            if symbol.endswith("USDT") and last_price > 0 and turnover >= min_turnover:
                eligible.append((turnover, symbol))
        eligible.sort(reverse=True)
        results = []
        failures = []
        for _, symbol in eligible[:top_n]:
            try:
                results.append(_load_symbol(symbol, limit))
            except HTTPException as exc:
                failures.append({"symbol": symbol, "status_code": exc.status_code, "detail": exc.detail})
        results.sort(key=lambda item: float(item.get("aggregate", {}).get("score", 0)), reverse=True)
        return {
            "results": results,
            "scanned": len(results) + len(failures),
            "failed": failures,
            "data_source": payload.get("_data_source", "unknown"),
            "bybit_error": payload.get("_bybit_error"),
            "execution": "DISABLED",
            "trading_enabled": False,
            "note": "Scores are heuristic analysis, not win probabilities. No orders are placed.",
        }
