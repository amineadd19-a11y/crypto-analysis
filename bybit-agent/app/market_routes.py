"""Bybit public market scan routes (analysis only)."""
from __future__ import annotations

import math

from fastapi import HTTPException, Query

from app.market_data import UpstreamMarketError, get_kline, get_tickers, raise_as_http


def register_market_routes(app, client, ALLOWED_INTERVALS, build_signal):
    _ = client

    @app.get("/api/market/tickers")
    def tickers(category: str = Query(default="linear", pattern="^(linear|spot)$")) -> dict:
        try:
            response = get_tickers(category=category)
            return {
                "category": category,
                "result": response.get("result", {}).get("list", []),
                "upstream_host": response.get("_resolved_host"),
                "data_source": response.get("_data_source", "unknown"),
                "bybit_error": response.get("_bybit_error"),
            }
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail={"error": "market_data_upstream", "message": "Unable to reach market data."})

    @app.get("/api/scan/top")
    def scan_top(
        interval: str = Query(default="5"),
        limit: int = Query(default=200, ge=200, le=500),
        top_n: int = Query(default=10, ge=1, le=20),
        min_turnover: float = Query(default=5_000_000, gt=0),
    ) -> dict:
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
                    klines = get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
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
                except UpstreamMarketError:
                    continue
                except Exception:
                    continue
            results.sort(key=lambda row: (row["signal"] != "WAIT", row["turnover24h"]), reverse=True)
            return {
                "category": "linear", "interval": interval, "scanned": len(results),
                "requested": top_n, "results": results, "execution": "DISABLED",
                "upstream_host": response.get("_resolved_host"),
                "data_source": response.get("_data_source", "unknown"),
                "bybit_error": response.get("_bybit_error"),
                "disclaimer": "Shortlist uses liquidity, then technical filters. No orders are placed. Source may be Bybit or OKX public.",
            }
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail={"error": "market_data_upstream", "message": "Unable to scan the futures shortlist."})

    @app.get("/api/scan")
    def scan(
        symbol: str = Query(default="BTCUSDT", min_length=3, max_length=30, pattern="^[A-Z0-9]+$"),
        interval: str = Query(default="5"),
        limit: int = Query(default=200, ge=200, le=1000),
    ) -> dict:
        if interval not in ALLOWED_INTERVALS:
            raise HTTPException(status_code=400, detail="Unsupported interval.")
        try:
            response = get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
            candles = response.get("result", {}).get("list", [])
            if len(candles) > 1:
                candles = candles[1:]
            candles = list(reversed(candles))
            closes = [float(candle[4]) for candle in candles]
            if not closes or any(not math.isfinite(value) or value <= 0 for value in closes):
                raise HTTPException(status_code=502, detail="Invalid candle data from upstream.")
            analysis = build_signal(closes)
            return {
                "symbol": symbol, "category": "linear", "interval": interval,
                "candles_used": len(closes), "analysis": analysis,
                "upstream_host": response.get("_resolved_host"),
                "data_source": response.get("_data_source", "unknown"),
                "bybit_error": response.get("_bybit_error"),
                "disclaimer": "Heuristic signal only. No orders are placed. data_source is Bybit or OKX public fallback.",
            }
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail={"error": "market_data_upstream", "message": "Unable to scan this symbol."})

    def _fetch_mtf_candles(symbol: str, limit: int = 200) -> tuple:
        from app.mtf_scanner import MTF_INTERVALS
        by_interval = {}
        data_source = "unknown"
        bybit_error = None
        for interval in MTF_INTERVALS:
            try:
                response = get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
                candles = response.get("result", {}).get("list", []) or []
                if len(candles) > 1:
                    candles = candles[1:]
                candles = list(reversed(candles))
                by_interval[interval] = candles
                data_source = response.get("_data_source", data_source)
                bybit_error = response.get("_bybit_error") or bybit_error
            except UpstreamMarketError as exc:
                by_interval[interval] = []
                bybit_error = getattr(exc, "kind", "upstream")
        return by_interval, data_source, bybit_error

    @app.get("/api/scan/mtf")
    def scan_mtf(
        symbol: str = Query(default="BTCUSDT", min_length=3, max_length=30, pattern="^[A-Z0-9]+$"),
        limit: int = Query(default=200, ge=60, le=300),
        min_score: float = Query(default=0, ge=0, le=100),
    ) -> dict:
        from app.mtf_scanner import analyze_symbol_mtf
        try:
            by_interval, data_source, bybit_error = _fetch_mtf_candles(symbol, limit=limit)
            result = analyze_symbol_mtf(symbol, by_interval, data_source=data_source)
            result["bybit_error"] = bybit_error
            if result.get("aggregate", {}).get("score", 0) < min_score:
                result["filtered"] = True
                result["filter_reason"] = f"Score below min_score={min_score}"
            return result
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail={"error": "mtf_scan_failed", "message": "Unable to run multi-timeframe scan."})

    @app.get("/api/scan/smart")
    def scan_smart(
        top_n: int = Query(default=8, ge=1, le=15),
        min_turnover: float = Query(default=3_000_000, gt=0),
        min_score: float = Query(default=55, ge=0, le=100),
        min_rel_volume: float = Query(default=1.5, ge=0),
        direction: str = Query(default="any", pattern="^(any|long|short)$"),
        limit: int = Query(default=120, ge=60, le=200),
        max_symbols: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        from app.mtf_scanner import analyze_symbol_mtf, screen_candidate_from_ticker
        try:
            response = get_tickers(category="linear")
            tickers_list = response.get("result", {}).get("list", []) or []
            data_source = response.get("_data_source", "unknown")
            bybit_error = response.get("_bybit_error")
            eligible = []
            for item in tickers_list:
                symbol = item.get("symbol", "")
                try:
                    turnover = float(item.get("turnover24h", 0))
                    last_price = float(item.get("lastPrice", 0))
                    change = float(item.get("price24hPcnt", 0)) * 100
                except (TypeError, ValueError):
                    continue
                if not symbol.endswith("USDT") or last_price <= 0 or turnover < min_turnover:
                    continue
                eligible.append(screen_candidate_from_ticker(symbol, last_price, change, turnover))
            eligible.sort(key=lambda r: abs(r["change24h_pct"]), reverse=True)
            results = []
            rejected = []
            scanned = 0
            # Scan a broad, liquidity-ranked universe instead of stopping after a tiny shortlist.
            # max_symbols bounds serverless runtime; response reports whether the universe was truncated.
            candidate_universe = eligible[:max_symbols]
            for cand in candidate_universe:
                symbol = cand["symbol"]
                scanned += 1
                try:
                    by_interval, src, err = _fetch_mtf_candles(symbol, limit=limit)
                    analysis = analyze_symbol_mtf(symbol, by_interval, data_source=src or data_source)
                    agg = analysis.get("aggregate") or {}
                    score = float(agg.get("score") or 0)
                    direction_hit = agg.get("direction") or "none"
                    tf5 = (analysis.get("timeframes") or {}).get("5m") or {}
                    rel = tf5.get("relative_volume")
                    if rel is not None and rel < min_rel_volume and min_rel_volume > 0:
                        rejected.append({"symbol": symbol, "reason": f"rel_volume {rel:.2f} < {min_rel_volume}", "score": score})
                        continue
                    if score < min_score:
                        rejected.append({"symbol": symbol, "reason": f"score {score} < {min_score}", "score": score})
                        continue
                    if direction != "any" and direction_hit != direction:
                        rejected.append({"symbol": symbol, "reason": f"direction {direction_hit} != {direction}", "score": score})
                        continue
                    results.append({
                        "symbol": symbol, "price": cand["last_price"], "change24h_pct": round(cand["change24h_pct"], 2),
                        "turnover24h": cand["turnover24h"], "classification": agg.get("classification"),
                        "score": score, "confidence": agg.get("confidence"), "direction": direction_hit,
                        "conflicts": agg.get("conflicts"), "timeframe_alignment": agg.get("timeframe_alignment"),
                        "levels": analysis.get("levels"), "reasons_up": agg.get("reasons_up"),
                        "reasons_down": agg.get("reasons_down"), "data_source": analysis.get("data_source"),
                    })
                except Exception:
                    rejected.append({"symbol": symbol, "reason": "scan_error", "score": 0})
                    continue
            results.sort(key=lambda r: r["score"], reverse=True)
            results = results[:top_n]
            return {
                "category": "linear", "universe_total": len(eligible),
                "candidate_limit": max_symbols, "universe_truncated": len(eligible) > max_symbols,
                "scanned": scanned, "returned": len(results), "results": results,
                "rejected_sample": rejected[:20],
                "filters": {"min_turnover": min_turnover, "min_score": min_score, "min_rel_volume": min_rel_volume, "direction": direction},
                "data_source": data_source, "bybit_error": bybit_error, "execution": "DISABLED", "trading_enabled": False,
                "disclaimer": "Multi-timeframe heuristic ranking only. Not trading advice. No orders placed.",
            }
        except UpstreamMarketError as exc:
            raise_as_http(exc)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail={"error": "smart_scan_failed", "message": "Unable to run smart multi-timeframe scan."})
