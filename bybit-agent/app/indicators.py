"""Validated, dependency-free technical indicators for the analysis-only scanner.

All functions consume chronological candle arrays (oldest first). They never
fetch market data and never place orders.
"""
from __future__ import annotations

import math
from typing import Sequence


def _finite(values: Sequence[float], name: str = "values") -> list[float]:
    out = [float(v) for v in values]
    if any(not math.isfinite(v) for v in out):
        raise ValueError(f"{name} must contain only finite values")
    return out


def ema(values: Sequence[float], period: int) -> list[float]:
    """Return an EMA series seeded with the first observation."""
    xs = _finite(values)
    if period < 1:
        raise ValueError("period must be >= 1")
    if not xs:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [xs[0]]
    for value in xs[1:]:
        out.append(alpha * value + (1.0 - alpha) * out[-1])
    return out


def rsi(closes: Sequence[float], period: int = 14) -> float | None:
    """Wilder-style RSI using the most recent period of price changes."""
    xs = _finite(closes, "closes")
    if period < 1:
        raise ValueError("period must be >= 1")
    if len(xs) < period + 1:
        return None
    changes = [b - a for a, b in zip(xs[-period-1:-1], xs[-period:])]
    gains = sum(max(change, 0.0) for change in changes) / period
    losses = sum(max(-change, 0.0) for change in changes) / period
    if gains == 0.0 and losses == 0.0:
        return 50.0
    if losses == 0.0:
        return 100.0
    if gains == 0.0:
        return 0.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def macd_histogram(closes: Sequence[float]) -> float | None:
    """Latest MACD histogram (EMA12 - EMA26 - EMA9 signal)."""
    xs = _finite(closes, "closes")
    if len(xs) < 26:
        return None
    fast, slow = ema(xs, 12), ema(xs, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal = ema(line, 9)
    return line[-1] - signal[-1]


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> float | None:
    """Simple-average ATR over the most recent period of true ranges."""
    hs, ls, cs = _finite(highs, "highs"), _finite(lows, "lows"), _finite(closes, "closes")
    if period < 1:
        raise ValueError("period must be >= 1")
    if not (len(hs) == len(ls) == len(cs)):
        raise ValueError("highs, lows and closes must have equal lengths")
    if len(cs) < 2:
        return None
    if any(h < l for h, l in zip(hs, ls)):
        raise ValueError("each high must be >= its low")
    true_ranges = []
    for i in range(1, len(cs)):
        true_ranges.append(max(hs[i] - ls[i], abs(hs[i] - cs[i-1]), abs(ls[i] - cs[i-1])))
    if not true_ranges:
        return None
    window = true_ranges[-period:]
    return sum(window) / len(window)


def pct_change(values: Sequence[float], lookback: int = 1) -> float | None:
    xs = _finite(values)
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    if len(xs) <= lookback or xs[-lookback-1] == 0:
        return None
    return (xs[-1] / xs[-lookback-1] - 1.0) * 100.0


def relative_volume(volumes: Sequence[float], period: int = 20) -> float | None:
    """Latest volume divided by the mean of preceding volumes (excludes latest)."""
    xs = _finite(volumes, "volumes")
    if period < 1:
        raise ValueError("period must be >= 1")
    if len(xs) < 2:
        return None
    if any(v < 0 for v in xs):
        raise ValueError("volumes cannot be negative")
    baseline = xs[-period-1:-1]
    if not baseline:
        return None
    avg = sum(baseline) / len(baseline)
    if avg <= 0:
        return None
    return xs[-1] / avg


def swing_highs_lows(highs: Sequence[float], lows: Sequence[float], left_right: int = 2) -> tuple[list[float], list[float]]:
    """Return confirmed local pivot highs and lows, in chronological order."""
    hs, ls = _finite(highs, "highs"), _finite(lows, "lows")
    if len(hs) != len(ls):
        raise ValueError("highs and lows must have equal lengths")
    if left_right < 1:
        raise ValueError("left_right must be >= 1")
    pivot_highs: list[float] = []
    pivot_lows: list[float] = []
    w = left_right
    for i in range(w, len(hs) - w):
        hwin = hs[i-w:i+w+1]
        lwin = ls[i-w:i+w+1]
        if hs[i] == max(hwin) and hwin.count(hs[i]) == 1:
            pivot_highs.append(hs[i])
        if ls[i] == min(lwin) and lwin.count(ls[i]) == 1:
            pivot_lows.append(ls[i])
    return pivot_highs, pivot_lows


def structure_bias(highs: Sequence[float], lows: Sequence[float]) -> str:
    """Classify recent pivot structure as HH/HL, LH/LL, or mixed."""
    sh, sl = swing_highs_lows(highs, lows)
    if len(sh) < 2 or len(sl) < 2:
        return "mixed"
    higher_highs, lower_highs = sh[-1] > sh[-2], sh[-1] < sh[-2]
    higher_lows, lower_lows = sl[-1] > sl[-2], sl[-1] < sl[-2]
    if higher_highs and higher_lows:
        return "higher_highs_higher_lows"
    if lower_highs and lower_lows:
        return "lower_highs_lower_lows"
    return "mixed"


def vwap(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], volumes: Sequence[float]) -> float | None:
    """Cumulative typical-price VWAP for the supplied candle window."""
    hs, ls, cs, vs = (_finite(highs, "highs"), _finite(lows, "lows"),
                      _finite(closes, "closes"), _finite(volumes, "volumes"))
    if not (len(hs) == len(ls) == len(cs) == len(vs)):
        raise ValueError("OHLCV arrays must have equal lengths")
    if any(v < 0 for v in vs):
        raise ValueError("volumes cannot be negative")
    total = sum(vs)
    if total <= 0:
        return None
    return sum(((h + l + c) / 3.0) * vol for h, l, c, vol in zip(hs, ls, cs, vs)) / total


def adx(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> dict[str, float | None]:
    """Simple-smoothed ADX and directional indicators (+DI/-DI)."""
    hs, ls, cs = _finite(highs, "highs"), _finite(lows, "lows"), _finite(closes, "closes")
    if not (len(hs) == len(ls) == len(cs)):
        raise ValueError("OHLC arrays must have equal lengths")
    if period < 1:
        raise ValueError("period must be >= 1")
    if len(cs) < period + 2:
        return {"adx": None, "plus_di": None, "minus_di": None}
    tr, plus_dm, minus_dm = [], [], []
    for i in range(1, len(cs)):
        up, down = hs[i] - hs[i-1], ls[i-1] - ls[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(hs[i] - ls[i], abs(hs[i] - cs[i-1]), abs(ls[i] - cs[i-1])))
    trn = sum(tr[-period:]) / min(period, len(tr))
    if trn <= 0:
        return {"adx": 0.0, "plus_di": 0.0, "minus_di": 0.0}
    plus = 100.0 * (sum(plus_dm[-period:]) / min(period, len(plus_dm))) / trn
    minus = 100.0 * (sum(minus_dm[-period:]) / min(period, len(minus_dm))) / trn
    dxs = []
    start = max(0, len(tr) - period * 2)
    for end in range(max(period, start + 1), len(tr) + 1):
        span = slice(max(0, end-period), end)
        tr_avg = sum(tr[span]) / len(tr[span])
        p_avg = sum(plus_dm[span]) / len(plus_dm[span])
        m_avg = sum(minus_dm[span]) / len(minus_dm[span])
        pdi = 100.0 * p_avg / tr_avg if tr_avg else 0.0
        mdi = 100.0 * m_avg / tr_avg if tr_avg else 0.0
        denom = pdi + mdi
        dxs.append(100.0 * abs(pdi-mdi) / denom if denom else 0.0)
    return {"adx": sum(dxs[-period:]) / len(dxs[-period:]) if dxs else None,
            "plus_di": plus, "minus_di": minus}
