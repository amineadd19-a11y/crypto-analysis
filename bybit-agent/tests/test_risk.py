import unittest

from app.risk import calculate_order_qty, round_qty_down


class RiskTests(unittest.TestCase):
    def test_risk_budget_limits_quantity(self):
        qty = calculate_order_qty(
            equity_usdt=1000, entry_price=100, stop_price=98,
            risk_pct=0.5, max_notional_pct=100,
        )
        self.assertAlmostEqual(qty, 2.5)
        self.assertAlmostEqual(qty * (100 - 98), 5.0)

    def test_notional_cap_limits_quantity(self):
        qty = calculate_order_qty(
            equity_usdt=1000, entry_price=100, stop_price=99,
            risk_pct=0.5, max_notional_pct=10,
        )
        self.assertAlmostEqual(qty, 1.0)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            calculate_order_qty(
                equity_usdt=100, entry_price=10, stop_price=10, risk_pct=0.5
            )

    def test_qty_rounds_down(self):
        self.assertAlmostEqual(round_qty_down(1.239, 0.01), 1.23)


if __name__ == "__main__":
    unittest.main()
