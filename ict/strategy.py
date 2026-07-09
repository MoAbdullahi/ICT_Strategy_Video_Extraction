"""Walk-forward multi-timeframe ICT strategy engine.

Sequence per the video (short side; long side is the mirror image):

1. DAILY BIAS  — price taps into an unmitigated daily bearish FVG (or
   bearish BPR). The bias stays armed for ``bias_window`` 1H bars.
2. 1H CONFIRMATION — while the bias is armed, BOTH must occur:
   (a) FVG inversion: a recent bullish 1H FVG is closed through downward;
   (b) bearish CISD: a 1H close below the latest confirmed swing low.
3. ENTRY — short at the close of the bar completing the confirmation.
   STOP  — above the high of the move into the daily zone (+ buffer).
   TARGET — nearest resting sell-side liquidity (recent confirmed 1H swing
   low below entry) offering at least ``min_rr`` R; otherwise a fixed
   ``fallback_rr`` R target.

Everything is computed bar-by-bar with no lookahead: swings confirm N bars
after the pivot, daily zones only become usable the day after the daily
candle completes, and all lifecycle updates use completed bars only.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .bpr import bpr_from
from .fvg import FVG, fvg_at, update_lifecycle
from .structure import Swing, cisd_event, confirm_swings_at


@dataclass
class Params:
    swing_n: int = 2            # fractal width for swing points
    bias_window: int = 48       # 1H bars a bias stays armed after a zone tap
    h1_fvg_max_age: int = 24    # 1H FVG must have formed within this many bars
                                # before the bias opened to count as "the latest"
    stop_lookback: int = 24     # 1H bars defining the high/low "of the move"
    stop_buffer: float = 0.0002 # fractional buffer beyond the stop level
    target_lookback: int = 200  # how far back to scan for liquidity targets
    min_rr: float = 2.0         # liquidity target must offer at least this R
    fallback_rr: float = 3.0    # fixed-R target when no liquidity qualifies
    max_hold: int = 240         # 1H bars before a time-based exit at close
    risk_pct: float = 0.01      # fraction of equity risked per trade
    daily_bpr_max_age: int = 30 # max daily bars between overlapping FVGs


@dataclass
class Bias:
    direction: str              # 'bearish' | 'bullish'
    zone: FVG
    opened_idx: int
    inversion_done: bool = False
    cisd_done: bool = False


@dataclass
class OpenTrade:
    direction: str              # 'short' | 'long'
    entry_idx: int
    entry: float
    stop: float
    target: float
    rr_target: float
    zone_source: str


def _prepare_daily_zones(daily_df: pd.DataFrame, p: Params):
    """Detect all daily FVGs/BPRs; return [(available_from_date, zone), ...]."""
    highs = daily_df["high"].to_numpy()
    lows = daily_df["low"].to_numpy()
    dates = [ts.date() for ts in daily_df.index]
    all_fvgs: List[FVG] = []
    zones = []
    for i in range(len(daily_df)):
        f = fvg_at(highs, lows, i)
        if f is None:
            continue
        b = bpr_from(all_fvgs, f, p.daily_bpr_max_age)
        all_fvgs.append(f)
        zones.append((dates[i], f))
        if b is not None:
            zones.append((dates[i], b))
    return zones


def _pick_target(direction: str, entry: float, risk: float, swings: List[Swing],
                 t: int, p: Params):
    """Nearest resting liquidity beyond ``min_rr``; else fixed fallback R."""
    if direction == "short":
        candidates = [s for s in swings
                      if s.kind == "low" and s.price < entry and s.idx >= t - p.target_lookback]
        candidates.sort(key=lambda s: -s.price)  # nearest (highest) first
        for s in candidates:
            rr = (entry - s.price) / risk
            if rr >= p.min_rr:
                return s.price, rr
        return entry - p.fallback_rr * risk, p.fallback_rr
    candidates = [s for s in swings
                  if s.kind == "high" and s.price > entry and s.idx >= t - p.target_lookback]
    candidates.sort(key=lambda s: s.price)       # nearest (lowest) first
    for s in candidates:
        rr = (s.price - entry) / risk
        if rr >= p.min_rr:
            return s.price, rr
    return entry + p.fallback_rr * risk, p.fallback_rr


def run_strategy(daily_df: pd.DataFrame, h1_df: pd.DataFrame,
                 p: Optional[Params] = None) -> pd.DataFrame:
    """Run the full walk-forward strategy. Returns a DataFrame of trades."""
    p = p or Params()

    highs = h1_df["high"].to_numpy()
    lows = h1_df["low"].to_numpy()
    closes = h1_df["close"].to_numpy()
    times = h1_df.index
    h1_dates = [ts.date() for ts in times]

    pending_zones = sorted(_prepare_daily_zones(daily_df, p), key=lambda z: z[0])
    zone_ptr = 0
    active_zones: List[FVG] = []

    swings: List[Swing] = []       # all confirmed 1H swings, in confirmation order
    h1_fvgs: List[FVG] = []
    bias: Optional[Bias] = None
    open_trade: Optional[OpenTrade] = None
    trades = []

    def close_trade(trade: OpenTrade, t: int, exit_price: float, outcome: str):
        risk = abs(trade.stop - trade.entry)
        if trade.direction == "short":
            r = (trade.entry - exit_price) / risk
        else:
            r = (exit_price - trade.entry) / risk
        trades.append({
            "direction": trade.direction,
            "entry_time": times[trade.entry_idx],
            "exit_time": times[t],
            "entry": trade.entry,
            "stop": trade.stop,
            "target": trade.target,
            "exit": exit_price,
            "rr_target": trade.rr_target,
            "r": r,
            "outcome": outcome,
            "zone_source": trade.zone_source,
            "bars_held": t - trade.entry_idx,
        })

    for t in range(len(h1_df)):
        hi, lo, cl = highs[t], lows[t], closes[t]

        # --- release daily zones that became available before this bar's date
        while zone_ptr < len(pending_zones) and pending_zones[zone_ptr][0] < h1_dates[t]:
            active_zones.append(pending_zones[zone_ptr][1])
            zone_ptr += 1

        # --- manage open position first (stop checked before target: conservative)
        if open_trade is not None:
            tr = open_trade
            if tr.direction == "short":
                if hi >= tr.stop:
                    close_trade(tr, t, tr.stop, "stop")
                    open_trade = None
                elif lo <= tr.target:
                    close_trade(tr, t, tr.target, "target")
                    open_trade = None
            else:
                if lo <= tr.stop:
                    close_trade(tr, t, tr.stop, "stop")
                    open_trade = None
                elif hi >= tr.target:
                    close_trade(tr, t, tr.target, "target")
                    open_trade = None
            if open_trade is not None and t - tr.entry_idx >= p.max_hold:
                close_trade(tr, t, cl, "time")
                open_trade = None

        # --- structure updates for this completed bar
        swings.extend(confirm_swings_at(highs, lows, t, p.swing_n))
        swing_highs = [s for s in swings if s.kind == "high"]
        swing_lows = [s for s in swings if s.kind == "low"]
        cisd = cisd_event(cl, swing_highs, swing_lows)

        # --- 1H FVG bookkeeping: new gap + inversion events
        inversion_events = []       # directions confirmed by an inversion this bar
        for f in h1_fvgs:
            if update_lifecycle(f, hi, lo, cl, t):
                # a bullish FVG closed through downward confirms bearish flow
                inversion_events.append(("bearish" if f.direction == "bullish" else "bullish", f))
        new_h1 = fvg_at(highs, lows, t)
        if new_h1 is not None:
            h1_fvgs.append(new_h1)
        if len(h1_fvgs) > 500:
            h1_fvgs = h1_fvgs[-300:]

        # --- daily zone lifecycle against this 1H bar
        for z in active_zones:
            update_lifecycle(z, hi, lo, cl, t)
        if bias is not None and bias.zone.inverted:
            bias = None             # the daily zone failed; stand down

        # --- bias expiry
        if bias is not None and t - bias.opened_idx > p.bias_window:
            bias = None

        # --- arm (or re-arm) a bias on a fresh tap of a live daily zone
        if open_trade is None:
            for z in active_zones:
                if not z.alive or not z.contains(hi, lo):
                    continue
                direction = "bearish" if z.direction == "bearish" else "bullish"
                if bias is None or bias.zone is not z:
                    bias = Bias(direction, z, t)
                else:
                    bias.opened_idx = t   # still inside the zone: keep it armed
                break

        # --- confirmation flags
        if bias is not None:
            for ev_dir, f in inversion_events:
                if ev_dir == bias.direction and f.formed_idx >= bias.opened_idx - p.h1_fvg_max_age:
                    bias.inversion_done = True
            if cisd == bias.direction:
                bias.cisd_done = True

        # --- entry
        if (bias is not None and open_trade is None
                and bias.inversion_done and bias.cisd_done):
            lb = max(0, t - p.stop_lookback + 1)
            if bias.direction == "bearish":
                stop = float(np.max(highs[lb:t + 1])) * (1 + p.stop_buffer)
                entry = cl
                risk = stop - entry
                if risk > 0:
                    target, rr = _pick_target("short", entry, risk, swings, t, p)
                    open_trade = OpenTrade("short", t, entry, stop, target, rr,
                                           bias.zone.source)
            else:
                stop = float(np.min(lows[lb:t + 1])) * (1 - p.stop_buffer)
                entry = cl
                risk = entry - stop
                if risk > 0:
                    target, rr = _pick_target("long", entry, risk, swings, t, p)
                    open_trade = OpenTrade("long", t, entry, stop, target, rr,
                                           bias.zone.source)
            if open_trade is not None:
                bias.zone.consumed = True
            bias = None

    return pd.DataFrame(trades)
