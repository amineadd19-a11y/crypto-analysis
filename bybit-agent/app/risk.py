"""Pure risk helpers for linear USDT perpetuals; no exchange calls here."""
from __future__ import annotations

import math


def calculate_order_qty(
    *,
    equity_usdt: float,
    entry_price: float,
    stop_price: float,
    risk_pct: float = 0.5,
    max_notional_pct: float = 100.0,
) -> float:
    """Return raw quantity before exchange step-size rounding.

    Position risk is bounded by equity * risk_pct. max_notional_pct caps
    notional exposure relative to equity; leverage does not increase risk budget.
    """
    values = (equity_usdt, entry_price, stop_price, risk_pct, max_notional_pct)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("All inputs must be finite numbers.")
    if equity_usdt <= 0 or entry_price <= 0 or stop_price <= 0:
        raise ValueError("Equity and prices must be positive.")
    if entry_price == stop_price:
        raise ValueError("Stop price must differ from entry price.")
    if not 0 < risk_pct <= 1:
        raise ValueError("risk_pct must be greater than 0 and at most 1.")
    if not 0 < max_notional_pct <= 100:
        raise ValueError("max_notional_pct must be in (0, 100].")

    stop_distance_pct = abs(entry_price - stop_price) / entry_price
    risk_budget = equity_usdt * (risk_pct / 100.0)
    risk_limited_notional = risk_budget / stop_distance_pct
    notional_cap = equity_usdt * (max_notional_pct / 100.0)
    notional = min(risk_limited_notional, notional_cap)
    return notional / entry_price


def round_qty_down(qty: float, qty_step: float) -> float:
    """Round quantity down to the exchange's lot step; never round up."""
    if not math.isfinite(qty) or not math.isfinite(qty_step) or qty < 0 or qty_step <= 0:
        raise ValueError("qty must be non-negative and qty_step must be positive finite.")
    return math.floor((qty + 1e-12) / qty_step) * qty_step
