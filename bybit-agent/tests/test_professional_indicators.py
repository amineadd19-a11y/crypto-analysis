"""Regression tests for the professional indicator module; deterministic, no network."""
import unittest

from app.indicators import adx, atr, ema, macd_histogram, pct_change, relative_volume, rsi, structure_bias, swing_highs_lows, vwap


class ProfessionalIndicatorTests(unittest.TestCase):
    def test_flat_series_is_neutral_or_zero(self):
        xs = [10.0] * 220
        self.assertEqual(ema(xs, 20), xs)
        self.assertEqual(rsi(xs), 50.0)
        self.assertAlmostEqual(macd_histogram(xs), 0.0, places=10)

    def test_rsi_extremes_and_short_data(self):
        self.assertIsNone(rsi([1.0, 2.0], 14))
        self.assertEqual(rsi([float(i) for i in range(20)]), 100.0)
        self.assertEqual(rsi([float(20-i) for i in range(20)]), 0.0)

    def test_atr_validates_lengths_and_calculates(self):
        highs, lows, closes = [11, 12, 13], [9, 10, 11], [10, 11, 12]
        self.assertAlmostEqual(atr(highs, lows, closes, 2), 2.0)
        with self.assertRaises(ValueError):
            atr(highs, lows, closes[:-1], 2)

    def test_relative_volume_excludes_current_candle(self):
        self.assertAlmostEqual(relative_volume([100.0] * 20 + [300.0], 20), 3.0)
        self.assertIsNone(relative_volume([0.0, 0.0, 10.0], 2))

    def test_pct_change_and_invalid_inputs(self):
        self.assertAlmostEqual(pct_change([100.0, 110.0], 1), 10.0)
        with self.assertRaises(ValueError):
            ema([1.0, float("nan")], 2)

    def test_vwap_and_adx_have_expected_shapes(self):
        highs = [10.5 + i * 0.1 for i in range(40)]
        lows = [9.5 + i * 0.1 for i in range(40)]
        closes = [10.0 + i * 0.1 for i in range(40)]
        volumes = [100.0] * 40
        self.assertIsNotNone(vwap(highs, lows, closes, volumes))
        result = adx(highs, lows, closes, 14)
        self.assertIn("adx", result)
        self.assertIn("plus_di", result)
        self.assertIn("minus_di", result)
        self.assertIsNone(adx(highs[:5], lows[:5], closes[:5], 14)["adx"])

    def test_swing_helpers_return_lists_and_string_bias(self):
        highs = [1, 2, 1, 3, 2, 4, 3, 5, 4]
        lows = [0, 1, 0.5, 1.5, 1, 2, 1.5, 3, 2.5]
        pivot_highs, pivot_lows = swing_highs_lows(highs, lows, 1)
        self.assertTrue(pivot_highs)
        self.assertTrue(pivot_lows)
        self.assertIn(structure_bias(highs, lows), {"higher_highs_higher_lows", "lower_highs_lower_lows", "mixed"})


if __name__ == "__main__":
    unittest.main()
