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

    def test_displacement_filter_keeps_level_live(self):
        from ict.structure import Swing
        swing_lows = [Swing("low", 10, 1.00)]
        # weak body: no event, level NOT consumed
        self.assertIsNone(cisd_event(0.999, [], swing_lows,
                                     body=0.0001, atr=0.001, min_body_atr=0.5))
        self.assertFalse(swing_lows[0].broken)
        # displacement close later still fires on the same level
        self.assertEqual(cisd_event(0.995, [], swing_lows,
                                    body=0.0008, atr=0.001, min_body_atr=0.5),
                         "bearish")
        self.assertTrue(swing_lows[0].broken)


class TestIndicators(unittest.TestCase):
    def test_atr_basic(self):
        from ict.indicators import atr
        highs = np.array([1.2, 1.3, 1.25])
        lows = np.array([1.0, 1.1, 1.15])
        closes = np.array([1.1, 1.2, 1.2])
        a = atr(highs, lows, closes, n=14)
        self.assertAlmostEqual(a[0], 0.2)           # first bar: range
        self.assertAlmostEqual(a[1], 0.2)           # TRs: 0.2, 0.2 -> mean 0.2
        self.assertAlmostEqual(a[2], (0.2 + 0.2 + 0.1) / 3)


class TestFilters(unittest.TestCase):
    def test_entry_allowed_killzone_and_days(self):
        import pandas as pd
        from ict.strategy import Params, _entry_allowed
        p = Params(killzones=((7, 10), (12, 15)), allowed_days=(0, 1, 3))
        tue_8utc = pd.Timestamp("2026-01-06 08:00", tz="UTC")     # Tuesday
        wed_8utc = pd.Timestamp("2026-01-07 08:00", tz="UTC")     # Wednesday
        tue_11utc = pd.Timestamp("2026-01-06 11:00", tz="UTC")
        self.assertTrue(_entry_allowed(tue_8utc, p))
        self.assertFalse(_entry_allowed(wed_8utc, p))              # day blocked
        self.assertFalse(_entry_allowed(tue_11utc, p))             # hour blocked
        # tz conversion: 09:00 +01:00 == 08:00 UTC -> allowed
        self.assertTrue(_entry_allowed(pd.Timestamp("2026-01-06 09:00+01:00"), p))

    def test_entry_allowed_news_buffer(self):
        import pandas as pd
        from ict.strategy import Params, _entry_allowed
        news = [pd.Timestamp("2026-01-06 13:30", tz="UTC")]
        p = Params(news_times=news, news_buffer_min=60)
        self.assertFalse(_entry_allowed(pd.Timestamp("2026-01-06 13:00", tz="UTC"), p))
        self.assertTrue(_entry_allowed(pd.Timestamp("2026-01-06 15:00", tz="UTC"), p))


class TestPartialTargets(unittest.TestCase):
    def test_pick_targets_partial_between_rr1_and_main(self):
        from ict.strategy import Params, _pick_targets
        from ict.structure import Swing
        p = Params(partial_targets=True, partial_rr1=1.0, min_rr=2.0)
        entry, risk = 1.100, 0.010
        swings = [
            Swing("low", 50, 1.088),   # 1.2R -> partial target
            Swing("low", 60, 1.075),   # 2.5R -> main target
        ]
        t1, rr1, t2, rr2 = _pick_targets("short", entry, risk, swings, 100, p)
        self.assertAlmostEqual(t2, 1.075)
        self.assertAlmostEqual(rr2, 2.5)
        self.assertAlmostEqual(t1, 1.088)
        self.assertAlmostEqual(rr1, 1.2)

    def test_pick_targets_fallback_when_no_liquidity(self):
        from ict.strategy import Params, _pick_targets
        p = Params(partial_targets=True)
        t1, rr1, t2, rr2 = _pick_targets("short", 1.100, 0.010, [], 100, p)
        self.assertAlmostEqual(t2, 1.100 - 3.0 * 0.010)
        self.assertAlmostEqual(rr2, 3.0)
        self.assertIsNone(t1)


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
