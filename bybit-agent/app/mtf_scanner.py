"""Multi-timeframe analysis scanner. Analysis-only; never places orders."""
from __future__ import annotations

import math
import time
from typing import Any

from app.indicators import atr, ema, macd_histogram, pct_change, relative_volume, rsi, structure_bias, swing_highs_lows

MTF_INTERVALS = ("1", "5", "15", "60", "240")
INTERVAL_LABEL = {"1": "1m", "5": "5m", "15": "15m", "60": "1h", "240": "4h"}

DEFAULT_CFG = {
    "min_move_1m_pct": 3.0,
    "min_move_5m_pct": 7.0,
    "min_rel_volume": 3.0,
    "min_score": 55,
    "min_rr": 1.5,
    "atr_stop_mult": 1.5,
    "rr_targets": (1.5, 2.5, 4.0),
    "max_extension_atr": 4.0,
    "min_candles": 60,
    "prefer_candles": 200,
}


def _parse_candles(raw: list) -> dict[str, list[float]] | None:
    if not raw:
        return None
    rows = list(raw)
    try:
        if len(rows) > 1 and float(rows[0][0]) > float(rows[-1][0]):
            rows = list(reversed(rows))
    except (TypeError, ValueError, IndexError):
        pass
    opens, highs, lows, closes, volumes, timestamps = [], [], [], [], [], []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        try:
            ts = float(row[0])
            o, h, l, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
            vol = float(row[5]) if len(row) > 5 else 0.0
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(x) for x in (o, h, l, c)) or min(o, h, l, c) <= 0:
            continue
        timestamps.append(ts)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        volumes.append(vol if math.isfinite(vol) and vol >= 0 else 0.0)
    if len(closes) < 10:
        return None
    return {"timestamps": timestamps, "opens": opens, "highs": highs, "lows": lows, "closes": closes, "volumes": volumes}


def analyze_timeframe(candles_raw: list, interval: str, cfg: dict | None = None) -> dict[str, Any]:
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    parsed = _parse_candles(candles_raw)
    label = INTERVAL_LABEL.get(interval, interval)
    if parsed is None:
        return {"interval": interval, "label": label, "status": "NO_TRADE_INSUFFICIENT_DATA", "bias": "neutral", "reasons": ["Insufficient or malformed candles"], "data_quality": "poor"}
    closes, highs, lows, volumes = parsed["closes"], parsed["highs"], parsed["lows"], parsed["volumes"]
    n = len(closes)
    quality = "good" if n >= cfg["prefer_candles"] else ("ok" if n >= cfg["min_candles"] else "poor")
    reasons: list[str] = []
    if quality == "poor":
        reasons.append(f"Only {n} candles (prefer {cfg['prefer_candles']})")
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    e200 = ema(closes, 200) if n >= 200 else []
    last = closes[-1]
    r = rsi(closes, 14)
    hist = macd_histogram(closes)
    atr14 = atr(highs, lows, closes, 14)
    move = pct_change(closes, min(20, n - 1))
    rel_vol = relative_volume(volumes, 20) if any(v > 0 for v in volumes) else None
    struct = structure_bias(highs, lows)
    sh, sl = swing_highs_lows(highs, lows)
    bull_trend = e20 and e50 and last > e20[-1] > e50[-1]
    bear_trend = e20 and e50 and last < e20[-1] < e50[-1]
    if e200:
        if last > e200[-1] and bull_trend:
            reasons.append("Price above EMA200 with short EMAs stacked bullish")
        elif last < e200[-1] and bear_trend:
            reasons.append("Price below EMA200 with short EMAs stacked bearish")
    bias = "neutral"
    if bull_trend and r is not None and r >= 50 and hist is not None and hist > 0:
        bias = "bullish"
        reasons.append("EMA stack + RSI + MACD agree bullish")
    elif bear_trend and r is not None and r <= 50 and hist is not None and hist < 0:
        bias = "bearish"
        reasons.append("EMA stack + RSI + MACD agree bearish")
    elif bull_trend:
        bias = "bullish_weak"
        reasons.append("EMA stack bullish but momentum not confirmed")
    elif bear_trend:
        bias = "bearish_weak"
        reasons.append("EMA stack bearish but momentum not confirmed")
    else:
        reasons.append("No aligned trend/momentum on this TF")
    if struct == "higher_highs_higher_lows":
        reasons.append("Structure: higher highs and higher lows")
    elif struct == "lower_highs_lower_lows":
        reasons.append("Structure: lower highs and lower lows")
    support = sl[-1] if sl else (min(lows[-20:]) if n >= 20 else min(lows))
    resistance = sh[-1] if sh else (max(highs[-20:]) if n >= 20 else max(highs))
    return {
        "interval": interval, "label": label, "status": "ok", "bias": bias, "last_close": last,
        "ema20": e20[-1] if e20 else None, "ema50": e50[-1] if e50 else None, "ema200": e200[-1] if e200 else None,
        "rsi14": round(r, 2) if r is not None else None, "macd_histogram": hist, "atr14": atr14,
        "pct_change_lookback": move, "relative_volume": rel_vol, "structure": struct,
        "support": support, "resistance": resistance, "candle_count": n, "data_quality": quality,
        "reasons": reasons, "timestamp_ms": parsed["timestamps"][-1] if parsed["timestamps"] else None,
    }


def _bias_score(bias: str) -> int:
    return {"bullish": 2, "bullish_weak": 1, "neutral": 0, "bearish_weak": -1, "bearish": -2}.get(bias, 0)


def aggregate_mtf(tf_results: dict[str, dict], cfg: dict | None = None) -> dict[str, Any]:
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    reasons_up: list[str] = []
    reasons_down: list[str] = []
    weights = {"1": 1.0, "5": 1.5, "15": 2.0, "60": 2.5, "240": 3.0}
    score = 50.0
    alignment = 0.0
    weight_sum = 0.0
    usable = 0
    for interval, res in tf_results.items():
        if res.get("status") != "ok":
            reasons_down.append(f"{INTERVAL_LABEL.get(interval, interval)}: insufficient data")
            continue
        usable += 1
        w = weights.get(interval, 1.0)
        b = _bias_score(str(res.get("bias", "neutral")))
        alignment += b * w
        weight_sum += w
        if res.get("data_quality") == "poor":
            score -= 5
            reasons_down.append(f"{res['label']}: poor data quality")
        rel = res.get("relative_volume")
        if rel is not None and rel >= cfg["min_rel_volume"]:
            score += 6
            reasons_up.append(f"{res['label']}: relative volume {rel:.1f}x")
        move = res.get("pct_change_lookback")
        if move is not None and abs(move) >= 5:
            score += 3 if move > 0 else -3
    if usable < 2:
        return {"classification": "NO_TRADE_INSUFFICIENT_DATA", "score": 0, "confidence": "low", "direction": "none", "reasons_up": [], "reasons_down": reasons_down + ["Need at least 2 usable timeframes"], "timeframe_alignment": {}, "conflicts": True, "execution": "DISABLED"}
    norm = alignment / weight_sum if weight_sum else 0
    score += norm * 12
    short = [_bias_score(tf_results[i]["bias"]) for i in ("1", "5") if tf_results.get(i, {}).get("status") == "ok"]
    long = [_bias_score(tf_results[i]["bias"]) for i in ("60", "240") if tf_results.get(i, {}).get("status") == "ok"]
    conflicts = False
    if short and long:
        if (sum(short) / len(short) > 0.5 and sum(long) / len(long) < -0.5) or (sum(short) / len(short) < -0.5 and sum(long) / len(long) > 0.5):
            conflicts = True
            score -= 15
            reasons_down.append("Short-term bias conflicts with higher-timeframe trend (countertrend)")
    score = max(0.0, min(100.0, score))
    if score >= 75 and norm > 0.8 and not conflicts:
        classification, direction = "STRONG_LONG_CANDIDATE", "long"
    elif score >= 60 and norm > 0.3:
        classification, direction = "LONG_CANDIDATE", "long"
    elif score <= 25 and norm < -0.8 and not conflicts:
        classification, direction = "STRONG_SHORT_CANDIDATE", "short"
    elif score <= 40 and norm < -0.3:
        classification, direction = "SHORT_CANDIDATE", "short"
    else:
        classification, direction = "NEUTRAL", "none"
    qualities = [tf_results[i].get("data_quality") for i in tf_results if tf_results[i].get("status") == "ok"]
    if qualities.count("good") >= 2:
        confidence = "medium_high"
    elif "poor" in qualities or usable < 3:
        confidence = "low"
    else:
        confidence = "medium"
    alignment_map = {INTERVAL_LABEL.get(i, i): tf_results[i].get("bias") for i in MTF_INTERVALS if i in tf_results}
    return {"classification": classification, "score": round(score, 1), "confidence": confidence, "direction": direction, "reasons_up": reasons_up, "reasons_down": reasons_down, "timeframe_alignment": alignment_map, "conflicts": conflicts, "norm_bias": round(norm, 3), "execution": "DISABLED", "disclaimer": "Score is a transparent heuristic (0-100), not a predicted win rate."}


def build_levels(tf_results: dict[str, dict], direction: str, cfg: dict | None = None) -> dict[str, Any]:
    """Build structure-aware, analysis-only levels; never manufacture a tradable setup."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    primary_key = next((k for k in ("15", "5", "60", "1") if tf_results.get(k, {}).get("status") == "ok"), None)
    primary = tf_results.get(primary_key) if primary_key else None
    if primary is None or direction not in ("long", "short"):
        return {"available": False, "status": "NOT_AVAILABLE", "entry_status": "NO_VALID_DIRECTION", "reason": "No direction or primary timeframe", "execution": "DISABLED"}

    price = float(primary["last_close"])
    atr_v = primary.get("atr14")
    support, resistance = primary.get("support"), primary.get("resistance")
    base = {
        "available": False, "status": "NOT_AVAILABLE", "entry_status": "WAIT_FOR_BETTER_ENTRY",
        "reference_price": round(price, 8), "reference_timestamp_ms": primary.get("timestamp_ms"),
        "atr14": round(float(atr_v), 8) if atr_v is not None else None,
        "support": support, "resistance": resistance, "execution": "DISABLED",
    }
    if atr_v is None or not math.isfinite(float(atr_v)) or float(atr_v) <= 0:
        return {**base, "reason": "ATR unavailable or invalid; no levels calculated"}

    atr_v = float(atr_v)
    ema50 = primary.get("ema50")
    if ema50 and abs(price - float(ema50)) / atr_v > cfg["max_extension_atr"]:
        dist = abs(price - float(ema50)) / atr_v
        return {**base, "reason": f"Price extended {dist:.1f} ATR from EMA50 (max {cfg['max_extension_atr']}); wait for price to return toward structure"}

    stop_dist = float(cfg["atr_stop_mult"]) * atr_v
    if not math.isfinite(stop_dist) or stop_dist <= 0:
        return {**base, "reason": "Invalid ATR stop distance"}

    if direction == "long":
        stop = price - stop_dist
        if support is not None and 0 < float(support) < price:
            stop = min(stop, float(support) - 0.1 * atr_v)
        risk = price - stop
        structural_targets = []
        if resistance is not None and float(resistance) > price:
            structural_targets.append(float(resistance))
        # ATR projections are estimates, but do not disguise nearby resistance as a valid target.
        targets = [price + risk * float(r) for r in cfg["rr_targets"]]
        target1_rr = (targets[0] - price) / risk if risk > 0 else None
        pullback_ref = float(ema50) if ema50 is not None else None
        pullback_zone = [round(pullback_ref - 0.15 * atr_v, 8), round(pullback_ref + 0.15 * atr_v, 8)] if pullback_ref and price < pullback_ref < price + 2 * atr_v else None
        valid_geometry = stop < price and all(t > price for t in targets)
        invalidation = stop
    else:
        stop = price + stop_dist
        if resistance is not None and float(resistance) > price:
            stop = max(stop, float(resistance) + 0.1 * atr_v)
        risk = stop - price
        structural_targets = []
        if support is not None and 0 < float(support) < price:
            structural_targets.append(float(support))
        targets = [price - risk * float(r) for r in cfg["rr_targets"]]
        target1_rr = (price - targets[0]) / risk if risk > 0 else None
        pullback_ref = float(ema50) if ema50 is not None else None
        pullback_zone = [round(pullback_ref - 0.15 * atr_v, 8), round(pullback_ref + 0.15 * atr_v, 8)] if pullback_ref and price - 2 * atr_v < pullback_ref < price else None
        valid_geometry = stop > price and all(0 < t < price for t in targets)
        invalidation = stop

    if not valid_geometry or not math.isfinite(risk) or risk <= 0:
        return {**base, "reason": "Invalid level geometry; entry, stop and targets fail directional validation"}
    if target1_rr is None or target1_rr < float(cfg["min_rr"]):
        result = {
            **base,
            "reason": f"Risk/reward {target1_rr:.2f} below minimum {cfg['min_rr']}" if target1_rr is not None else "Risk/reward could not be calculated",
            "indicative_stop": round(stop, 8),
            "risk_reward_first_target": round(target1_rr, 2) if target1_rr is not None else None,
        }
        if pullback_zone:
            result["suggested_entry_zone"] = pullback_zone
            result["suggested_entry_note"] = "EMA50-based pullback reference only; wait for price confirmation. Not an active entry."
        return result

    # Keep projected targets transparent and verify the first target clears the configured RR floor.
    entry_zone = [round(price * 0.999, 8), round(price, 8)] if direction == "long" else [round(price, 8), round(price * 1.001, 8)]
    return {
        "available": True, "status": "VALID_ESTIMATE", "entry_status": "LEVELS_VALID_NOT_AN_ORDER",
        "reference_price": round(price, 8), "entry_price": round(price, 8),
        "reference_timestamp_ms": primary.get("timestamp_ms"), "entry_zone": entry_zone,
        "invalidation": round(invalidation, 8), "stop_loss": round(stop, 8),
        "take_profit": [round(t, 8) for t in targets],
        "tp1": round(targets[0], 8) if len(targets) > 0 else None,
        "tp2": round(targets[1], 8) if len(targets) > 1 else None,
        "tp3": round(targets[2], 8) if len(targets) > 2 else None,
        "risk_reward_first_target": round(target1_rr, 2),
        "atr14": round(atr_v, 8), "support": support, "resistance": resistance,
        "structural_target_reference": structural_targets[0] if structural_targets else None,
        "assumptions": [f"ATR stop multiple={cfg['atr_stop_mult']}", f"Targets at R:R {list(cfg['rr_targets'])}", "Fees/slippage not deducted; estimates only", "Targets are projections, not guaranteed fills", "Not an order instruction"],
        "execution": "DISABLED",
    }


def screen_candidate_from_ticker(symbol: str, last_price: float, change24h_pct: float, turnover24h: float, cfg: dict | None = None) -> dict[str, Any]:
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    flags = []
    if abs(change24h_pct) >= cfg["min_move_5m_pct"]:
        flags.append("large_24h_move")
    if turnover24h >= 5_000_000:
        flags.append("liquid")
    return {"symbol": symbol, "last_price": last_price, "change24h_pct": change24h_pct, "turnover24h": turnover24h, "prefilter_flags": flags, "pass_liquidity": turnover24h >= 1_000_000 and last_price > 0}


def analyze_symbol_mtf(symbol: str, candles_by_interval: dict[str, list], cfg: dict | None = None, data_source: str = "unknown") -> dict[str, Any]:
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    tf_results = {}
    for interval in MTF_INTERVALS:
        raw = candles_by_interval.get(interval) or []
        tf_results[interval] = analyze_timeframe(raw, interval, cfg)
    agg = aggregate_mtf(tf_results, cfg)
    levels = build_levels(tf_results, agg["direction"], cfg)
    if not levels.get("available") and agg["classification"] not in ("NEUTRAL", "NO_TRADE_INSUFFICIENT_DATA"):
        agg["reasons_down"] = list(agg.get("reasons_down") or []) + [f"Levels rejected: {levels.get('reason', 'n/a')}"]
        if agg["score"] >= 60:
            agg["score"] = max(45, agg["score"] - 10)
            if agg["classification"].startswith("STRONG_"):
                agg["classification"] = agg["classification"].replace("STRONG_", "")
    return {"symbol": symbol, "analyzed_at_ms": int(time.time() * 1000), "data_source": data_source, "timeframes": {INTERVAL_LABEL[i]: tf_results[i] for i in MTF_INTERVALS if i in tf_results}, "aggregate": agg, "levels": levels, "execution": "DISABLED", "trading_enabled": False}
