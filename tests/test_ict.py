"""Unit tests for the ICT detection primitives (run: python -m unittest)."""

import unittest

import numpy as np

from ict.bpr import bpr_from
from ict.fvg import FVG, fvg_at, update_lifecycle
from ict.structure import cisd_event, confirm_swings_at


class TestFVG(unittest.TestCase):
    def test_bullish_fvg(self):
        # up-move: candle1 high (1.00) < candle3 low (1.20)
        highs = np.array([1.00, 1.15, 1.30])
        lows = np.array([0.95, 1.05, 1.20])
        f = fvg_at(highs, lows, 2)
        self.assertIsNotNone(f)
        self.assertEqual(f.direction, "bullish")
        self.assertAlmostEqual(f.bottom, 1.00)
        self.assertAlmostEqual(f.top, 1.20)

    def test_bearish_fvg(self):
        # down-move: candle1 low (1.20) > candle3 high (1.00)
        highs = np.array([1.30, 1.15, 1.00])
        lows = np.array([1.20, 1.05, 0.90])
        f = fvg_at(highs, lows, 2)
        self.assertIsNotNone(f)
        self.assertEqual(f.direction, "bearish")
        self.assertAlmostEqual(f.bottom, 1.00)
        self.assertAlmostEqual(f.top, 1.20)

    def test_no_fvg_when_overlapping(self):
        highs = np.array([1.10, 1.12, 1.11])
        lows = np.array([1.00, 1.02, 1.05])
        self.assertIsNone(fvg_at(highs, lows, 2))

    def test_mitigation_and_inversion(self):
        f = FVG("bullish", bottom=1.00, top=1.20, formed_idx=2)
        # bar dips into the zone -> mitigated, not inverted
        self.assertFalse(update_lifecycle(f, high=1.25, low=1.10, close=1.22, idx=3))
        self.assertTrue(f.mitigated)
        self.assertFalse(f.inverted)
        # bar closes below the bottom -> inversion event
        self.assertTrue(update_lifecycle(f, high=1.15, low=0.90, close=0.95, idx=4))
        self.assertTrue(f.inverted)
        self.assertEqual(f.inverted_idx, 4)

    def test_lifecycle_ignores_bars_at_or_before_formation(self):
        f = FVG("bullish", bottom=1.00, top=1.20, formed_idx=2)
        self.assertFalse(update_lifecycle(f, high=1.15, low=0.90, close=0.95, idx=2))
        self.assertFalse(f.inverted)


class TestBPR(unittest.TestCase):
    def test_overlap_creates_bpr_with_later_direction(self):
        bull = FVG("bullish", bottom=1.00, top=1.20, formed_idx=5)
        bear = FVG("bearish", bottom=1.10, top=1.30, formed_idx=8)
        b = bpr_from([bull], bear, max_age=30)
        self.assertIsNotNone(b)
        self.assertEqual(b.direction, "bearish")
        self.assertEqual(b.source, "bpr")
        self.assertAlmostEqual(b.bottom, 1.10)
        self.assertAlmostEqual(b.top, 1.20)

    def test_no_bpr_without_overlap(self):
        bull = FVG("bullish", bottom=1.00, top=1.05, formed_idx=5)
        bear = FVG("bearish", bottom=1.10, top=1.30, formed_idx=8)
        self.assertIsNone(bpr_from([bull], bear, max_age=30))

    def test_no_bpr_when_too_old(self):
        bull = FVG("bullish", bottom=1.00, top=1.20, formed_idx=5)
        bear = FVG("bearish", bottom=1.10, top=1.30, formed_idx=50)
        self.assertIsNone(bpr_from([bull], bear, max_age=30))


class TestStructure(unittest.TestCase):
    def test_swing_high_confirmed_n_bars_later(self):
        #                    0     1     2     3     4
        highs = np.array([1.00, 1.05, 1.20, 1.10, 1.02])
        lows = np.array([0.90, 0.95, 1.10, 1.00, 0.92])
        # pivot at index 2 confirms at t = 4 (n=2)
        self.assertEqual(confirm_swings_at(highs, lows, 3, n=2), [])
        swings = confirm_swings_at(highs, lows, 4, n=2)
        self.assertEqual(len(swings), 1)
        self.assertEqual(swings[0].kind, "high")
        self.assertEqual(swings[0].idx, 2)
        self.assertAlmostEqual(swings[0].price, 1.20)

    def test_swing_low(self):
        highs = np.array([1.20, 1.15, 1.05, 1.12, 1.18])
        lows = np.array([1.10, 1.02, 0.90, 1.00, 1.08])
        swings = confirm_swings_at(highs, lows, 4, n=2)
        self.assertEqual(len(swings), 1)
        self.assertEqual(swings[0].kind, "low")
        self.assertAlmostEqual(swings[0].price, 0.90)

    def test_bearish_cisd_fires_once(self):
        from ict.structure import Swing
        swing_lows = [Swing("low", 10, 1.00)]
        self.assertIsNone(cisd_event(1.05, [], swing_lows))     # above: no break
        self.assertEqual(cisd_event(0.99, [], swing_lows), "bearish")
        self.assertIsNone(cisd_event(0.98, [], swing_lows))     # already broken

    def test_bullish_cisd(self):
        from ict.structure import Swing
        swing_highs = [Swing("high", 10, 1.00)]
        self.assertEqual(cisd_event(1.01, swing_highs, []), "bullish")


class TestStrategyEndToEnd(unittest.TestCase):
    def test_runs_on_synthetic_data(self):
        """Smoke test: the engine runs on random-walk data without errors."""
        import pandas as pd
        from ict.strategy import run_strategy

        rng = np.random.default_rng(7)
        n_days, bars_per_day = 120, 24
        n = n_days * bars_per_day
        steps = rng.normal(0, 0.0008, n).cumsum()
        close = 1.10 + steps
        high = close + rng.uniform(0.0001, 0.0012, n)
        low = close - rng.uniform(0.0001, 0.0012, n)
        open_ = np.concatenate([[close[0]], close[:-1]])
        idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
        h1 = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)

        daily = h1.resample("1D").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        ).dropna()

        trades = run_strategy(daily, h1)
        # No assertion on trade count (data is random); every produced trade
        # must be internally consistent though.
        for _, tr in trades.iterrows():
            if tr["direction"] == "short":
                self.assertGreater(tr["stop"], tr["entry"])
                self.assertLess(tr["target"], tr["entry"])
            else:
                self.assertLess(tr["stop"], tr["entry"])
                self.assertGreater(tr["target"], tr["entry"])


if __name__ == "__main__":
    unittest.main()
