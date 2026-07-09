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


def cisd_event(close: float, swing_highs: List[Swing], swing_lows: List[Swing]) -> Optional[str]:
    """Check whether this bar's close breaks the most recent unbroken swing.

    Returns 'bearish' if the close breaks the latest unbroken swing low,
    'bullish' if it breaks the latest unbroken swing high, else None.
    Marks the broken swing so each level fires at most once.
    """
    event = None
    for s in reversed(swing_lows):
        if not s.broken:
            if close < s.price:
                s.broken = True
                event = "bearish"
            break
    for s in reversed(swing_highs):
        if not s.broken:
            if close > s.price:
                s.broken = True
                event = event or "bullish"
            break
    return event
