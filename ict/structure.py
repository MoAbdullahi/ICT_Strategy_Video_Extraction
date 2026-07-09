"""Market structure: swing points and Change In State of Delivery (CISD).

A swing high at bar ``i`` (fractal, N bars each side) is only *confirmed*
N bars later, at bar ``i + N``. All detection here is walk-forward safe:
``confirm_swings_at`` is called once per completed bar and only ever looks
backward from that bar.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Swing:
    kind: str        # 'high' | 'low'
    idx: int         # bar index of the pivot itself
    price: float
    broken: bool = False   # a close has traded through this level


def confirm_swings_at(highs, lows, t: int, n: int = 2) -> List[Swing]:
    """Return swings whose pivot sits at bar ``t - n`` and is confirmed at ``t``."""
    i = t - n
    if i < n:
        return []
    out: List[Swing] = []
    if all(highs[i] > highs[i - j] for j in range(1, n + 1)) and all(
        highs[i] > highs[i + j] for j in range(1, n + 1)
    ):
        out.append(Swing("high", i, float(highs[i])))
    if all(lows[i] < lows[i - j] for j in range(1, n + 1)) and all(
        lows[i] < lows[i + j] for j in range(1, n + 1)
    ):
        out.append(Swing("low", i, float(lows[i])))
    return out


def cisd_event(close: float, swing_highs: List[Swing], swing_lows: List[Swing],
               body: float = 0.0, atr: float = 0.0,
               min_body_atr: float = 0.0) -> Optional[str]:
    """Check whether this bar's close breaks the most recent unbroken swing.

    Returns 'bearish' if the close breaks the latest unbroken swing low,
    'bullish' if it breaks the latest unbroken swing high, else None.
    Marks the broken swing so each level fires at most once.

    Displacement filter: when ``min_body_atr`` > 0, the breaking candle's
    body must be at least ``min_body_atr * atr``. A weak close through the
    level does NOT consume it — the level stays live until a displacement
    close takes it out, which filters "wick games" and shallow breaks.
    """
    displaced = min_body_atr <= 0 or (atr > 0 and body >= min_body_atr * atr)
    event = None
    for s in reversed(swing_lows):
        if not s.broken:
            if close < s.price and displaced:
                s.broken = True
                event = "bearish"
            break
    for s in reversed(swing_highs):
        if not s.broken:
            if close > s.price and displaced:
                s.broken = True
                event = event or "bullish"
            break
    return event


def smt_ok(direction: str, own_highs: List[float], own_lows: List[float],
           other_highs: List[float], other_lows: List[float],
           inverse: bool = True) -> bool:
    """SMT (Smart Money Technique) divergence check against a correlated asset.

    ``direction`` is the intended trade ('bearish' = short). Lists hold the
    last confirmed swing prices in chronological order; at least two of each
    relevant kind are required, otherwise the check fails (no divergence
    evidence -> no trade when the filter is on).

    Short example, inverse asset (EURUSD vs DXY): EURUSD sweeps to a higher
    high while DXY *fails* to make the corresponding lower low -> divergence
    confirms the short. ``inverse=False`` compares like-for-like extremes
    (e.g. EURUSD vs GBPUSD: one makes the extreme, the other fails).
    """
    if direction == "bearish":
        if len(own_highs) < 2:
            return False
        if own_highs[-1] <= own_highs[-2]:      # no higher high on the traded asset
            return False
        if inverse:
            return len(other_lows) >= 2 and other_lows[-1] >= other_lows[-2]
        return len(other_highs) >= 2 and other_highs[-1] <= other_highs[-2]
    if len(own_lows) < 2:
        return False
    if own_lows[-1] >= own_lows[-2]:            # no lower low on the traded asset
        return False
    if inverse:
        return len(other_highs) >= 2 and other_highs[-1] <= other_highs[-2]
    return len(other_lows) >= 2 and other_lows[-1] >= other_lows[-2]
