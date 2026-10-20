"""Pure technical indicators for analysis-only scanning. No trading."""
from __future__ import annotations

import math
from typing import Sequence


def ema(values: Sequence[float], period: int) -> list[float]:
    if not values or period < 1:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [float(values[0])]
    for value in values[1:]:
        out.append(alpha * float(value) + (1.0 - alpha) * out[-1])
    return out


def rsi(values: Sequence[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for before, after in zip(values[:-1], values[1:]):
        change = float(after) - float(before)
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


def macd_histogram(values: Sequence[float]) -> float | None:
    if len(values) < 35:
        return None
    fast = ema(values, 12)
    slow = ema(values, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal = ema(line, 9)
    return line[-1] - signal[-1]


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> float | None:
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, n):
        h, l, prev_c = float(highs[i]), float(lows[i]), float(closes[i - 1])
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def pct_change(closes: Sequence[float], lookback: int) -> float | None:
    if len(closes) <= lookback or lookback < 1:
        return None
    base = float(closes[-1 - lookback])
    if base <= 0:
        return None
    return (float(closes[-1]) - base) / base * 100.0


def relative_volume(volumes: Sequence[float], lookback: int = 20) -> float | None:
    if len(volumes) < lookback + 1 or lookback < 1:
        return None
    baseline = sum(float(v) for v in volumes[-(lookback + 1) : -1]) / lookback
    if baseline <= 0:
        return None
    return float(volumes[-1]) / baseline


def swing_highs_lows(highs: Sequence[float], lows: Sequence[float], left: int = 2, right: int = 2) -> tuple[list[float], list[float]]:
    sh: list[float] = []
    sl: list[float] = []
    n = min(len(highs), len(lows))
    for i in range(left, n - right):
        h = float(highs[i])
        l = float(lows[i])
        if all(h >= float(highs[i - j]) for j in range(1, left + 1)) and all(h >= float(highs[i + j]) for j in range(1, right + 1)):
            sh.append(h)
        if all(l <= float(lows[i - j]) for j in range(1, left + 1)) and all(l <= float(lows[i + j]) for j in range(1, right + 1)):
            sl.append(l)
    return sh, sl


def structure_bias(highs: Sequence[float], lows: Sequence[float]) -> str:
    sh, sl = swing_highs_lows(highs, lows)
    if len(sh) < 2 or len(sl) < 2:
        return "insufficient"
    hh = sh[-1] > sh[-2]
    hl = sl[-1] > sl[-2]
    lh = sh[-1] < sh[-2]
    ll = sl[-1] < sl[-2]
    if hh and hl:
        return "higher_highs_higher_lows"
    if lh and ll:
        return "lower_highs_lower_lows"
    return "mixed"


def finite_positive(values: Sequence[float]) -> bool:
    return all(math.isfinite(float(v)) and float(v) > 0 for v in values)
