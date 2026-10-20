import math
import unittest

from app.risk import calculate_order_qty, round_qty_down


class RiskEdgeCaseTests(unittest.TestCase):
    def test_position_risk_matches_budget_when_stop_is_wide_enough(self):
        qty = calculate_order_qty(
            equity_usdt=1000,
            entry_price=100,
            stop_price=95,
            risk_pct=0.5,
            max_notional_pct=100,
        )
        self.assertAlmostEqual(qty * abs(100 - 95), 5.0)

    def test_notional_cap_limits_large_position(self):
        qty = calculate_order_qty(
            equity_usdt=100,
            entry_price=10,
            stop_price=9.99,
            risk_pct=1,
            max_notional_pct=20,
        )
        self.assertLessEqual(qty * 10, 20.0 + 1e-9)

    def test_rejects_nan_and_infinite_inputs(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_order_qty(
                        equity_usdt=100,
                        entry_price=value,
                        stop_price=90,
                    )

    def test_rejects_risk_above_one_percent(self):
        with self.assertRaises(ValueError):
            calculate_order_qty(
                equity_usdt=100,
                entry_price=10,
                stop_price=9,
                risk_pct=1.01,
            )

    def test_rounding_never_rounds_quantity_up(self):
        self.assertAlmostEqual(round_qty_down(1.239, 0.01), 1.23)
        self.assertAlmostEqual(round_qty_down(0.009, 0.01), 0.0)

    def test_rounding_rejects_invalid_step(self):
        with self.assertRaises(ValueError):
            round_qty_down(1, 0)
        with self.assertRaises(ValueError):
            round_qty_down(1, math.nan)


if __name__ == "__main__":
    unittest.main()
