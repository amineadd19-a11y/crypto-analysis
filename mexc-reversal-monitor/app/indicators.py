from __future__ import annotations
import pandas as pd
import numpy as np


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["ema20"] = x.close.ewm(span=20, adjust=False).mean()
    delta = x.close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
    rs = gain / loss
    x["rsi"] = 100 - (100 / (1 + rs))
    typical = (x.high + x.low + x.close) / 3
    x["vwap"] = (typical * x.volume).cumsum() / x.volume.cumsum().replace(0, np.nan)
    x["vol_ma20"] = x.volume.rolling(20).mean()
    x["ret1"] = x.close.pct_change(1) * 100
    x["ret5"] = x.close.pct_change(5) * 100
    x["body"] = (x.close - x.open).abs()
    x["range"] = (x.high - x.low).replace(0, np.nan)
    x["upper_wick"] = x.high - x[["open", "close"]].max(axis=1)
    x["lower_wick"] = x[["open", "close"]].min(axis=1) - x.low
    return x


def setup(df: pd.DataFrame, direction: str, min_score: int = 70) -> dict | None:
    if len(df) < 30:
        return None
    x = enrich(df).dropna(subset=["ema20", "rsi", "vwap", "vol_ma20"])
    if len(x) < 10:
        return None
    c = x.iloc[-1]
    prev = x.iloc[-2]
    score = 0
    reasons: list[str] = []
    price = float(c.close)
    move1 = float(c.ret1)
    move5 = float(c.ret5)
    vol_ratio = float(c.volume / c.vol_ma20) if c.vol_ma20 else 0
    ema_ext = (price / c.ema20 - 1) * 100
    vwap_ext = (price / c.vwap - 1) * 100

    if direction == "SHORT":
        if move1 >= 3: score += 15; reasons.append(f"1m +{move1:.2f}%")
        if move5 >= 7: score += 20; reasons.append(f"5m +{move5:.2f}%")
        if vol_ratio >= 3: score += 15; reasons.append(f"volume {vol_ratio:.1f}x")
        if ema_ext >= 2: score += 10; reasons.append(f"EMA20 +{ema_ext:.2f}%")
        if vwap_ext >= 2: score += 10; reasons.append(f"VWAP +{vwap_ext:.2f}%")
        wick_ratio = float(c.upper_wick / c.range)
        if wick_ratio >= 0.25 or (c.close < c.open and prev.close > prev.open):
            score += 15; reasons.append("rejection / momentum weakening")
        if c.rsi >= 70 and c.rsi < prev.rsi:
            score += 15; reasons.append(f"RSI rolling over {c.rsi:.0f}")
        if score < min_score or move1 < 1.0 or move5 < 3.0:
            return None
        entry_low = max(price * 0.995, float(c.ema20))
        entry_high = price * 1.015
        invalid = max(float(c.high), price * 1.035)
        risk = invalid - entry_low
        tp1 = entry_low - risk * 1.0
        tp2 = entry_low - risk * 2.0
        tp3 = entry_low - risk * 3.0
    else:
        move1, move5 = -move1, -move5
        if move1 >= 3: score += 15; reasons.append(f"1m -{move1:.2f}%")
        if move5 >= 7: score += 20; reasons.append(f"5m -{move5:.2f}%")
        if vol_ratio >= 3: score += 15; reasons.append(f"volume {vol_ratio:.1f}x")
        if ema_ext <= -2: score += 10; reasons.append(f"EMA20 {ema_ext:.2f}%")
        if vwap_ext <= -2: score += 10; reasons.append(f"VWAP {vwap_ext:.2f}%")
        wick_ratio = float(c.lower_wick / c.range)
        if wick_ratio >= 0.25 or (c.close > c.open and prev.close < prev.open):
            score += 15; reasons.append("rejection / momentum weakening")
        if c.rsi <= 30 and c.rsi > prev.rsi:
            score += 15; reasons.append(f"RSI recovering {c.rsi:.0f}")
        if score < min_score or move1 < 1.0 or move5 < 3.0:
            return None
        entry_low = price * 0.985
        entry_high = min(price * 1.005, float(c.ema20))
        invalid = min(float(c.low), price * 0.965)
        risk = entry_high - invalid
        tp1 = entry_high + risk * 1.0
        tp2 = entry_high + risk * 2.0
        tp3 = entry_high + risk * 3.0

    return {
        "direction": direction, "score": min(score, 100), "price": price,
        "entry_low": min(entry_low, entry_high), "entry_high": max(entry_low, entry_high),
        "invalid": invalid, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "rsi": float(c.rsi), "vol_ratio": vol_ratio, "move1": move1, "move5": move5,
        "reasons": reasons,
    }
