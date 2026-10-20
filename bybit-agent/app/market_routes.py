"""Bybit public market scan routes (analysis only)."""
from __future__ import annotations

import math

from fastapi import HTTPException, Query

from app.market_data import UpstreamMarketError, get_kline, get_tickers, raise_as_http


def register_market_routes(app, client, ALLOWED_INTERVALS, build_signal):
    # `client` (pybit) is retained for compatibility; public market reads use urllib
    # via market_data so upstream HTTP status and CloudFront blocks are visible.
    _ = client

    @app.get("/api/market/tickers")
    def tickers(category: str = Query(default="linear", pattern="^(linear|spot)$")) -> dict:
        try:
            response = get_tickers(category=category)
            return {
                "category": category,
                "result": response.get("result", {}).get("list", []),
                "upstream_host": response.get("_resolved_host"),
            }
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "market_data_upstream",
                    "message": "Unable to reach Bybit market data.",
                },
            )

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
            response = get_tickers(category="linear")
            tickers_list = response.get("result", {}).get("list", [])
            eligible = []
            for item in tickers_list:
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
                    klines = get_kline(
                        category="linear",
                        symbol=symbol,
                        interval=interval,
                        limit=limit,
                    )
                    candles = klines.get("result", {}).get("list", [])
                    if len(candles) > 1:
                        candles = candles[1:]
                    candles = list(reversed(candles))
                    closes = [float(row[4]) for row in candles]
                    if len(closes) < 200 or any(not math.isfinite(v) or v <= 0 for v in closes):
                        continue
                    analysis = build_signal(closes)
                    results.append(
                        {
                            "symbol": symbol,
                            "price": last_price,
                            "change24h_pct": round(change, 2),
                            "turnover24h": turnover,
                            "signal": analysis["signal"],
                            "rsi14": analysis["rsi14"],
                            "ema20": analysis["ema20"],
                            "ema50": analysis["ema50"],
                            "reasons": analysis["reasons"],
                        }
                    )
                except UpstreamMarketError:
                    continue
                except Exception:
                    continue
            results.sort(
                key=lambda row: (row["signal"] != "WAIT", row["turnover24h"]),
                reverse=True,
            )
            return {
                "category": "linear",
                "interval": interval,
                "scanned": len(results),
                "requested": top_n,
                "results": results,
                "execution": "DISABLED",
                "upstream_host": response.get("_resolved_host"),
                "disclaimer": "Shortlist uses liquidity, then technical filters. No orders are placed.",
            }
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "market_data_upstream",
                    "message": "Unable to scan the Bybit futures shortlist.",
                },
            )

    @app.get("/api/scan")
    def scan(
        symbol: str = Query(default="BTCUSDT", min_length=3, max_length=30, pattern="^[A-Z0-9]+$"),
        interval: str = Query(default="5"),
        limit: int = Query(default=200, ge=200, le=1000),
    ) -> dict:
        if interval not in ALLOWED_INTERVALS:
            raise HTTPException(status_code=400, detail="Unsupported interval.")
        try:
            response = get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                limit=limit,
            )
            candles = response.get("result", {}).get("list", [])
            if len(candles) > 1:
                candles = candles[1:]
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
                "upstream_host": response.get("_resolved_host"),
                "disclaimer": (
                    "Heuristic signal only. No orders are placed; "
                    "validate with backtests and demo trading."
                ),
            }
        except UpstreamMarketError as exp:
            raise_as_http(exp)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "market_data_upstream",
                    "message": "Unable to scan this symbol. Check the symbol and retry.",
                },
            )
