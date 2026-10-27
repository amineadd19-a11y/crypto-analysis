"""Deterministic tests for multi-timeframe scanner. No network, no credentials."""
from __future__ import annotations

import unittest

from app.indicators import atr, ema, pct_change, relative_volume, rsi
from app.mtf_scanner import analyze_symbol_mtf, analyze_timeframe, build_levels


def _synth_trend(n: int = 220, start: float = 100.0, step: float = 0.4, noise: float = 0.05) -> list:
    rows = []
    price = start
    for i in range(n):
        price = price + step + (noise if i % 3 == 0 else -noise * 0.5)
        o = price - 0.1
        h = price + 0.3
        l = price - 0.3
        c = price
        vol = 1000 + (i % 10) * 50
        rows.append([1_700_000_000_000 + i * 60_000, o, h, l, c, vol])
    return rows


def _synth_down(n: int = 220, start: float = 200.0) -> list:
    return _synth_trend(n=n, start=start, step=-0.45, noise=0.05)


class IndicatorTests(unittest.TestCase):
    def test_ema_rises_on_uptrend(self):
        closes = [float(i) for i in range(1, 50)]
        e = ema(closes, 10)
        self.assertGreater(e[-1], e[0])

    def test_rsi_none_on_short_series(self):
        self.assertIsNone(rsi([1, 2, 3], 14))

    def test_atr_positive(self):
        highs = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
        lows = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
        a = atr(highs, lows, closes, 14)
        self.assertIsNotNone(a)
        self.assertGreater(a, 0)

    def test_pct_change(self):
        closes = [100.0] * 10 + [110.0]
        self.assertAlmostEqual(pct_change(closes, 1) or 0, 10.0, places=5)

    def test_relative_volume_spike(self):
        vols = [100.0] * 20 + [400.0]
        self.assertAlmostEqual(relative_volume(vols, 20) or 0, 4.0, places=5)

    def test_malformed_rejects(self):
        res = analyze_timeframe([], "5")
        self.assertEqual(res["status"], "NO_TRADE_INSUFFICIENT_DATA")


class MtfAggregateTests(unittest.TestCase):
    def test_uptrend_prefers_long(self):
        up = _synth_trend()
        by = {i: up for i in ("1", "5", "15", "60", "240")}
        out = analyze_symbol_mtf("TESTUSDT", by, data_source="fixture")
        self.assertEqual(out["execution"], "DISABLED")
        self.assertFalse(out["trading_enabled"])
        self.assertIn(out["aggregate"]["direction"], ("long", "none"))
        self.assertGreaterEqual(out["aggregate"]["score"], 40)

    def test_downtrend_prefers_short_or_neutral(self):
        down = _synth_down()
        by = {i: down for i in ("1", "5", "15", "60", "240")}
        out = analyze_symbol_mtf("TESTUSDT", by, data_source="fixture")
        self.assertIn(out["aggregate"]["direction"], ("short", "none"))
        self.assertEqual(out["execution"], "DISABLED")

    def test_conflict_lowers_score(self):
        up = _synth_trend()
        down = _synth_down()
        by = {"1": up, "5": up, "15": up, "60": down, "240": down}
        out = analyze_symbol_mtf("TESTUSDT", by)
        self.assertTrue(out["aggregate"]["conflicts"])

    def test_insufficient_data(self):
        by = {i: [] for i in ("1", "5", "15", "60", "240")}
        out = analyze_symbol_mtf("X", by)
        self.assertEqual(out["aggregate"]["classification"], "NO_TRADE_INSUFFICIENT_DATA")

    def test_levels_disabled_when_no_direction(self):
        flat = [[1_700_000_000_000 + i * 60_000, 100, 100.2, 99.8, 100, 1000] for i in range(80)]
        by = {i: flat for i in ("1", "5", "15", "60", "240")}
        out = analyze_symbol_mtf("FLAT", by)
        if out["aggregate"]["direction"] == "none":
            self.assertFalse(out["levels"].get("available", False))

    def test_build_levels_rejects_bad_rr(self):
        tf = {
            "15": {
                "status": "ok",
                "last_close": 100.0,
                "atr14": 0.01,
                "support": 99.9,
                "resistance": 100.1,
                "timestamp_ms": 1,
                "ema50": 100.0,
            }
        }
        levels = build_levels(tf, "long", {"min_rr": 100, "atr_stop_mult": 1.5, "rr_targets": (1.5,), "max_extension_atr": 10})
        self.assertFalse(levels.get("available"))

    def test_low_structural_rr_waits_instead_of_publishing_levels(self):
        tf = {
            "15": {
                "status": "ok", "last_close": 100.0, "atr14": 1.0,
                "support": 99.8, "resistance": 100.5,
                "timestamp_ms": 1, "ema50": 100.0,
            }
        }
        levels = build_levels(tf, "long", {"min_rr": 1.5, "atr_stop_mult": 1.5, "rr_targets": (1.5, 2.5, 4.0), "max_extension_atr": 10})
        self.assertFalse(levels["available"])
        self.assertEqual(levels["entry_status"], "WAIT_FOR_BETTER_ENTRY")
        self.assertIn("Risk/reward", levels["reason"])
        self.assertEqual(levels["reference_price"], 100.0)
        self.assertEqual(levels["execution"], "DISABLED")

    def test_short_levels_have_correct_direction(self):
        tf = {
            "15": {
                "status": "ok", "last_close": 100.0, "atr14": 1.0,
                "support": 90.0, "resistance": 101.0,
                "timestamp_ms": 1, "ema50": 100.0,
            }
        }
        levels = build_levels(tf, "short", {"min_rr": 1.5, "atr_stop_mult": 1.5, "rr_targets": (1.5, 2.5, 4.0), "max_extension_atr": 10})
        self.assertTrue(levels["available"])
        self.assertGreater(levels["stop_loss"], levels["entry_price"])
        self.assertLess(levels["tp1"], levels["entry_price"])
        self.assertLess(levels["tp2"], levels["entry_price"])
        self.assertLess(levels["tp3"], levels["entry_price"])
        self.assertEqual(levels["execution"], "DISABLED")

    def test_trading_always_disabled(self):
        up = _synth_trend()
        out = analyze_symbol_mtf("BTCUSDT", {i: up for i in ("1", "5", "15", "60", "240")})
        self.assertEqual(out["execution"], "DISABLED")
        self.assertFalse(out["trading_enabled"])
        self.assertEqual(out["aggregate"]["execution"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
