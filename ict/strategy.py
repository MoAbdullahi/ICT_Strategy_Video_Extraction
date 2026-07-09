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

Optional refinements (all off by default — see STRATEGY.md):

- KILLZONES     — only enter during defined UTC hour windows.
- DAY FILTER    — only enter on given weekdays (in-sample-derived; beware).
- NEWS FILTER   — no entries within a buffer around supplied news times.
- FVG QUALITY   — the inverted 1H FVG must have formed with displacement
  (candle-2 body >= ``min_fvg_quality`` x ATR).
- DISPLACEMENT CISD — the structure-breaking candle needs a real body
  (>= ``cisd_min_body_atr`` x ATR); weak closes don't consume the level.
- PARTIAL TARGETS — take half off at the nearest liquidity (>= ``partial_rr1``
  R), move the stop to breakeven, run the rest to the main target.

Everything is computed bar-by-bar with no lookahead: swings confirm N bars
after the pivot, daily zones only become usable the day after the daily
candle completes, and all lifecycle updates use completed bars only.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .bpr import bpr_from
from .fvg import FVG, fvg_at, update_lifecycle
from .indicators import atr as atr_indicator
from .structure import Swing, cisd_event, confirm_swings_at, smt_ok


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

    # --- optional contextual filters (all off by default) ---
    killzones: Optional[Sequence[Tuple[int, int]]] = None
                                # UTC hour windows [start, end), e.g. ((7,10),(12,15))
    allowed_days: Optional[Sequence[int]] = None
                                # weekdays 0=Mon..6=Sun; None = all days
    news_times: Optional[Sequence[pd.Timestamp]] = None
                                # UTC timestamps of high-impact events
    news_buffer_min: int = 60   # no entries within +/- this many minutes of news

    # --- optional logic refinements (off by default) ---
    min_fvg_quality: float = 0.0    # displacement body / ATR of the inverted 1H FVG
    cisd_min_body_atr: float = 0.0  # CISD breaking-candle body >= this x ATR
    partial_targets: bool = False   # two-stage exits with breakeven move
    partial_rr1: float = 1.0        # min R for the first (partial) target
    atr_n: int = 14                 # ATR period for the displacement measures

    # --- Power of 3: entry only after the daily-open manipulation leg ---
    po3: bool = False               # short: price must have traded above today's
                                    # open first (Judas swing); long: below it

    # --- cross-asset SMT divergence (e.g. EURUSD vs DXY) ---
    smt_df: Optional[pd.DataFrame] = None   # correlated asset 1H OHLC (UTC index)
    smt_inverse: bool = True        # True: inversely correlated (DXY vs EURUSD)
    smt_lookback_bars: int = 120    # swings older than this (1H bars) are ignored


@dataclass
class Bias:
    direction: str              # 'bearish' | 'bullish'
    zone: FVG
    opened_idx: int
    inversion_done: bool = False
    cisd_done: bool = False
    inv_quality: float = 0.0    # quality of the FVG whose inversion confirmed


@dataclass
class OpenTrade:
    direction: str              # 'short' | 'long'
    entry_idx: int
    entry: float
    stop: float
    target: float               # main (final) target
    rr_target: float
    zone_source: str
    t1: Optional[float] = None  # partial target (None = single-target mode)
    rr1: float = 0.0
    half_closed: bool = False
    realized_r: float = 0.0     # R banked by the partial exit
    risk0: float = 0.0          # initial risk in price units (fixed at entry)
    quality: float = 0.0        # FVG quality of the confirming inversion


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


def _liquidity_levels(direction: str, entry: float, swings: List[Swing],
                      t: int, p: Params) -> List[float]:
    """Confirmed swing levels beyond the entry, nearest first."""
    if direction == "short":
        levels = [s.price for s in swings
                  if s.kind == "low" and s.price < entry and s.idx >= t - p.target_lookback]
        return sorted(set(levels), reverse=True)
    levels = [s.price for s in swings
              if s.kind == "high" and s.price > entry and s.idx >= t - p.target_lookback]
    return sorted(set(levels))


def _pick_targets(direction: str, entry: float, risk: float, swings: List[Swing],
                  t: int, p: Params):
    """Return (t1, rr1, t2, rr2). t1 is None unless partial_targets is on
    and a nearer liquidity level exists between partial_rr1 and the main RR."""
    sign = -1.0 if direction == "short" else 1.0
    levels = _liquidity_levels(direction, entry, swings, t, p)

    def rr_of(price):
        return sign * (price - entry) / risk

    t2, rr2 = None, None
    for price in levels:
        rr = rr_of(price)
        if rr >= p.min_rr:
            t2, rr2 = price, rr
            break
    if t2 is None:
        rr2 = p.fallback_rr
        t2 = entry + sign * p.fallback_rr * risk

    t1, rr1 = None, 0.0
    if p.partial_targets:
        for price in levels:
            rr = rr_of(price)
            if p.partial_rr1 <= rr < rr2:
                t1, rr1 = price, rr
                break
    return t1, rr1, t2, rr2


def _entry_allowed(ts: pd.Timestamp, p: Params) -> bool:
    """Apply the contextual filters (killzone / day-of-week / news)."""
    ts_utc = ts.tz_convert("UTC") if ts.tzinfo is not None else ts
    if p.killzones is not None:
        if not any(start <= ts_utc.hour < end for start, end in p.killzones):
            return False
    if p.allowed_days is not None and ts_utc.weekday() not in p.allowed_days:
        return False
    if p.news_times:
        buffer = pd.Timedelta(minutes=p.news_buffer_min)
        for nt in p.news_times:
            if abs(ts_utc - nt) <= buffer:
                return False
    return True


def run_strategy(daily_df: pd.DataFrame, h1_df: pd.DataFrame,
                 p: Optional[Params] = None) -> pd.DataFrame:
    """Run the full walk-forward strategy. Returns a DataFrame of trades."""
    p = p or Params()

    opens = h1_df["open"].to_numpy()
    highs = h1_df["high"].to_numpy()
    lows = h1_df["low"].to_numpy()
    closes = h1_df["close"].to_numpy()
    times = h1_df.index
    h1_dates = [ts.date() for ts in times]
    atr = atr_indicator(highs, lows, closes, p.atr_n)

    pending_zones = sorted(_prepare_daily_zones(daily_df, p), key=lambda z: z[0])
    zone_ptr = 0
    active_zones: List[FVG] = []

    # Power of 3: running state of the current UTC day
    day_open = day_high = day_low = None
    cur_date = None

    # SMT: walk-forward swings on the correlated asset, aligned by timestamp
    smt_times = smt_highs = smt_lows = None
    smt_ptr = 0
    smt_sw_highs: List[Swing] = []
    smt_sw_lows: List[Swing] = []
    if p.smt_df is not None:
        smt_times = p.smt_df.index
        smt_highs = p.smt_df["high"].to_numpy()
        smt_lows = p.smt_df["low"].to_numpy()

    swings: List[Swing] = []       # all confirmed 1H swings, in confirmation order
    h1_fvgs: List[FVG] = []
    bias: Optional[Bias] = None
    open_trade: Optional[OpenTrade] = None
    trades = []

    def close_trade(trade: OpenTrade, t: int, exit_price: float, outcome: str,
                    fraction: float = 1.0):
        """Book the final exit; ``fraction`` is the position share still open."""
        sign = 1.0 if trade.direction == "long" else -1.0
        leg_r = sign * (exit_price - trade.entry) / trade.risk0
        total_r = trade.realized_r + fraction * leg_r
        trades.append({
            "direction": trade.direction,
            "entry_time": times[trade.entry_idx],
            "exit_time": times[t],
            "entry": trade.entry,
            "stop": trade.stop,
            "target": trade.target,
            "exit": exit_price,
            "rr_target": trade.rr_target,
            "r": total_r,
            "outcome": outcome,
            "zone_source": trade.zone_source,
            "bars_held": t - trade.entry_idx,
            "quality": trade.quality,
        })

    for t in range(len(h1_df)):
        hi, lo, cl = highs[t], lows[t], closes[t]

        # --- release daily zones that became available before this bar's date
        while zone_ptr < len(pending_zones) and pending_zones[zone_ptr][0] < h1_dates[t]:
            active_zones.append(pending_zones[zone_ptr][1])
            zone_ptr += 1

        # --- Power of 3: track today's open and the running extremes
        if h1_dates[t] != cur_date:
            cur_date = h1_dates[t]
            day_open, day_high, day_low = opens[t], hi, lo
        else:
            day_high = max(day_high, hi)
            day_low = min(day_low, lo)

        # --- SMT: fold in correlated-asset bars completed by now
        if smt_times is not None:
            while smt_ptr < len(smt_times) and smt_times[smt_ptr] <= times[t]:
                for s in confirm_swings_at(smt_highs, smt_lows, smt_ptr, p.swing_n):
                    (smt_sw_highs if s.kind == "high" else smt_sw_lows).append(s)
                smt_ptr += 1

        # --- manage open position first (stop checked before target: conservative)
        if open_trade is not None:
            tr = open_trade
            stop_hit = hi >= tr.stop if tr.direction == "short" else lo <= tr.stop
            t1_hit = (tr.t1 is not None and not tr.half_closed and
                      (lo <= tr.t1 if tr.direction == "short" else hi >= tr.t1))
            t2_hit = lo <= tr.target if tr.direction == "short" else hi >= tr.target

            if stop_hit:
                outcome = "be_stop" if tr.half_closed else "stop"
                fraction = 0.5 if tr.half_closed else 1.0
                close_trade(tr, t, tr.stop, outcome, fraction)
                open_trade = None
            elif t1_hit:
                # bank half at T1, stop to breakeven; T2 same-bar not credited
                tr.realized_r = 0.5 * tr.rr1
                tr.half_closed = True
                tr.stop = tr.entry
            elif t2_hit:
                fraction = 0.5 if tr.half_closed else 1.0
                close_trade(tr, t, tr.target, "target", fraction)
                open_trade = None
            if open_trade is not None and t - tr.entry_idx >= p.max_hold:
                fraction = 0.5 if tr.half_closed else 1.0
                close_trade(tr, t, cl, "time", fraction)
                open_trade = None

        # --- structure updates for this completed bar
        swings.extend(confirm_swings_at(highs, lows, t, p.swing_n))
        swing_highs = [s for s in swings if s.kind == "high"]
        swing_lows = [s for s in swings if s.kind == "low"]
        cisd = cisd_event(cl, swing_highs, swing_lows,
                          body=abs(cl - opens[t]), atr=float(atr[t]),
                          min_body_atr=p.cisd_min_body_atr)

        # --- 1H FVG bookkeeping: new gap + inversion events
        inversion_events = []       # (direction confirmed, fvg) this bar
        for f in h1_fvgs:
            if update_lifecycle(f, hi, lo, cl, t):
                inversion_events.append(("bearish" if f.direction == "bullish" else "bullish", f))
        new_h1 = fvg_at(highs, lows, t)
        if new_h1 is not None:
            body2 = abs(closes[t - 1] - opens[t - 1])
            new_h1.quality = body2 / atr[t - 1] if atr[t - 1] > 0 else 0.0
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
                if (ev_dir == bias.direction
                        and f.formed_idx >= bias.opened_idx - p.h1_fvg_max_age
                        and f.quality >= p.min_fvg_quality):
                    bias.inversion_done = True
                    bias.inv_quality = f.quality
            if cisd == bias.direction:
                bias.cisd_done = True

        # --- contextual gates that depend on market state (not just the clock)
        def state_gates_pass() -> bool:
            if p.po3:
                manipulated = (day_high > day_open if bias.direction == "bearish"
                               else day_low < day_open)
                if not manipulated:
                    return False
            if p.smt_df is not None:
                cutoff_own = t - p.smt_lookback_bars
                own_h = [s.price for s in swings if s.kind == "high" and s.idx >= cutoff_own]
                own_l = [s.price for s in swings if s.kind == "low" and s.idx >= cutoff_own]
                cutoff_ts = times[t] - pd.Timedelta(hours=p.smt_lookback_bars)
                oth_h = [s.price for s in smt_sw_highs if smt_times[s.idx] >= cutoff_ts]
                oth_l = [s.price for s in smt_sw_lows if smt_times[s.idx] >= cutoff_ts]
                if not smt_ok(bias.direction, own_h, own_l, oth_h, oth_l, p.smt_inverse):
                    return False
            return True

        # --- entry
        if (bias is not None and open_trade is None
                and bias.inversion_done and bias.cisd_done
                and _entry_allowed(times[t], p)
                and state_gates_pass()):
            lb = max(0, t - p.stop_lookback + 1)
            if bias.direction == "bearish":
                stop = float(np.max(highs[lb:t + 1])) * (1 + p.stop_buffer)
                entry = cl
                risk = stop - entry
                direction = "short"
            else:
                stop = float(np.min(lows[lb:t + 1])) * (1 - p.stop_buffer)
                entry = cl
                risk = entry - stop
                direction = "long"
            if risk > 0:
                t1, rr1, t2, rr2 = _pick_targets(direction, entry, risk, swings, t, p)
                open_trade = OpenTrade(direction, t, entry, stop, t2, rr2,
                                       bias.zone.source, t1=t1, rr1=rr1, risk0=risk,
                                       quality=bias.inv_quality)
                bias.zone.consumed = True
            bias = None

    return pd.DataFrame(trades)
