import math
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pybit.unified_trading import HTTP

app = FastAPI(
    title="Bybit AI Trader",
    version="0.1.0",
    description="Independent analysis-only scanner for Bybit USDT perpetual markets.",
)

# Public market data only. Trading routes are intentionally not implemented.
client = HTTP(
    testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true",
    timeout=10,
    force_retry=True,
    max_retries=2,
    retry_delay=1,
)
ALLOWED_INTERVALS = {"1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "W", "M"}


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains, losses = [], []
    for before, after in zip(values[:-1], values[1:]):
        change = after - before
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((period - 1) * avg_gain + gain) / period
        avg_loss = ((period - 1) * avg_loss + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_histogram(values: list[float]) -> float:
    if len(values) < 35:
        return 0.0
    fast = ema(values, 12)
    slow = ema(values, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal = ema(line, 9)
    return line[-1] - signal[-1]


def build_signal(closes: list[float]) -> dict:
    if len(closes) < 200:
        raise HTTPException(status_code=422, detail="Not enough candles; request at least 200 for EMA200.")
    if any(not math.isfinite(value) or value <= 0 for value in closes):
        raise HTTPException(status_code=422, detail="Close prices must be positive finite numbers.")
    e20, e50, e200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    last = closes[-1]
    current_rsi = rsi(closes)
    hist = macd_histogram(closes)
    reasons: list[str] = []

    # Conservative trend-following filters; this is a heuristic, not a profit guarantee.
    if last > e20[-1] > e50[-1] and current_rsi >= 50 and hist > 0:
        direction: Literal["LONG", "SHORT", "WAIT"] = "LONG"
        reasons = ["Close above EMA20 and EMA50", "EMA20 above EMA50", "RSI supports upward momentum", "MACD histogram positive"]
    elif last < e20[-1] < e50[-1] and current_rsi <= 50 and hist < 0:
        direction = "SHORT"
        reasons = ["Close below EMA20 and EMA50", "EMA20 below EMA50", "RSI supports downward momentum", "MACD histogram negative"]
    else:
        direction = "WAIT"
        reasons = ["Trend/momentum filters do not align; no trade signal"]

    return {
        "signal": direction,
        "last_close": last,
        "ema20": e20[-1],
        "ema50": e50[-1],
        "ema200": e200[-1],
        "rsi14": round(current_rsi, 2),
        "macd_histogram": hist,
        "reasons": reasons,
        "execution": "DISABLED",
    }


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).with_name("dashboard.html"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "bybit-ai-trader", "trading_enabled": False}


@app.get("/api/market/tickers")
def tickers(category: str = Query(default="linear", pattern="^(linear|spot)$")) -> dict:
    try:
        response = client.get_tickers(category=category)
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit market data request failed.")
        return {"category": category, "result": response.get("result", {}).get("list", [])}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to reach Bybit market data.")


@app.get("/api/scan/top")
def scan_top(
    interval: str = Query(default="5"),
    limit: int = Query(default=200, ge=200, le=500),
    top_n: int = Query(default=10, ge=1, le=20),
    min_turnover: float = Query(default=5_000_000, gt=0),
) -> dict:
    """Scan a bounded shortlist of liquid USDT perpetuals; analysis only."""
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail="Unsupported interval.")
    try:
        response = client.get_tickers(category="linear")
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit ticker request failed.")
        tickers = response.get("result", {}).get("list", [])
        eligible = []
        for item in tickers:
            symbol = item.get("symbol", "")
            try:
                turnover = float(item.get("turnover24h", 0))
                last_price = float(item.get("lastPrice", 0))
                change = float(item.get("price24hPcnt", 0)) * 100
            except (TypeError, ValueError):
                continue
            if symbol.endswith("USDT") and last_price > 0 and turnover >= min_turnover:
                eligible.append((turnover, symbol, last_price, change))
        eligible.sort(key=lambda row: row[0], reverse=True)
        results = []
        for turnover, symbol, last_price, change in eligible[:top_n]:
            try:
                klines = client.get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
                if klines.get("retCode") != 0:
                    continue
                candles = klines.get("result", {}).get("list", [])
                if len(candles) > 1:
                    candles = candles[1:]
                candles = list(reversed(candles))
                closes = [float(row[4]) for row in candles]
                if len(closes) < 200 or any(not math.isfinite(v) or v <= 0 for v in closes):
                    continue
                analysis = build_signal(closes)
                results.append({
                    "symbol": symbol, "price": last_price,
                    "change24h_pct": round(change, 2), "turnover24h": turnover,
                    "signal": analysis["signal"], "rsi14": analysis["rsi14"],
                    "ema20": analysis["ema20"], "ema50": analysis["ema50"],
                    "reasons": analysis["reasons"],
                })
            except Exception:
                continue
        results.sort(key=lambda row: (row["signal"] != "WAIT", row["turnover24h"]), reverse=True)
        return {
            "category": "linear", "interval": interval, "scanned": len(results),
            "requested": top_n, "results": results, "execution": "DISABLED",
            "disclaimer": "Shortlist uses liquidity, then technical filters. No orders are placed.",
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to scan the Bybit futures shortlist.")


@app.get("/api/scan")
def scan(
    symbol: str = Query(default="BTCUSDT", min_length=3, max_length=30, pattern="^[A-Z0-9]+$"),
    interval: str = Query(default="5"),
    limit: int = Query(default=200, ge=200, le=1000),
) -> dict:
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail="Unsupported interval.")
    try:
        response = client.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit rejected the market data request.")
        candles = response.get("result", {}).get("list", [])
        # Bybit returns newest-first; the first candle may still be forming.
        # Exclude it to avoid signals changing before the candle closes.
        if len(candles) > 1:
            candles = candles[1:]
        # Indicators require chronological order.
        candles = list(reversed(candles))
        closes = [float(candle[4]) for candle in candles]
        if not closes or any(not math.isfinite(value) or value <= 0 for value in closes):
            raise HTTPException(status_code=502, detail="Invalid candle data from Bybit.")
        analysis = build_signal(closes)
        return {
            "symbol": symbol,
            "category": "linear",
            "interval": interval,
            "candles_used": len(closes),
            "analysis": analysis,
            "disclaimer": "Heuristic signal only. No orders are placed; validate with backtests and demo trading.",
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to scan this symbol. Check the symbol and retry.")
