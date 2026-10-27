import unittest

from app.main import build_signal, ema, macd_histogram, rsi


class IndicatorTests(unittest.TestCase):
    def test_ema_returns_same_value_for_flat_series(self):
        self.assertEqual(ema([10.0] * 5, 3), [10.0] * 5)

    def test_rsi_flat_series_is_neutral(self):
        self.assertEqual(rsi([10.0] * 30), 50.0)

    def test_macd_flat_series_is_zero(self):
        self.assertAlmostEqual(macd_histogram([10.0] * 100), 0.0)

    def test_flat_market_does_not_create_trade_signal(self):
        signal = build_signal([10.0] * 200)
        self.assertEqual(signal["signal"], "WAIT")
        self.assertEqual(signal["execution"], "DISABLED")

    def test_signal_requires_enough_candles_for_ema200(self):
        with self.assertRaises(Exception):
            build_signal([10.0] * 100)

    def test_signal_rejects_non_finite_close(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=bad):
                with self.assertRaises(Exception):
                    build_signal([10.0] * 199 + [bad])

    def test_signal_rejects_zero_or_negative_close(self):
        for bad in (0.0, -1.0):
            with self.subTest(value=bad):
                with self.assertRaises(Exception):
                    build_signal([10.0] * 199 + [bad])


if __name__ == "__main__":
    unittest.main()
