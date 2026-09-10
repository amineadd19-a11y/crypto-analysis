import pandas as pd
from app.indicators import setup


def test_no_signal_on_flat_market():
    rows = []
    price = 100.0
    for i in range(60):
        rows.append({"ts": i * 60, "open": price, "high": price * 1.002, "low": price * .998, "close": price, "volume": 100})
    assert setup(pd.DataFrame(rows), "SHORT") is None


def test_short_signal_after_spike_and_rejection():
    rows = []
    price = 100.0
    for i in range(55):
        price *= 1.001
        rows.append({"ts": i * 60, "open": price/1.001, "high": price*1.002, "low": price*.999, "close": price, "volume": 100})
    for i in range(5):
        o = price
        price *= 1.018
        rows.append({"ts": (55+i)*60, "open": o, "high": price*1.03, "low": o*.998, "close": price, "volume": 1000})
    assert setup(pd.DataFrame(rows), "SHORT", 50) is not None
