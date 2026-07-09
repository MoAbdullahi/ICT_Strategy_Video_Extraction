"""Fair Value Gap (FVG) detection and lifecycle tracking.

Convention (standard ICT):
- Bullish FVG forms in an up-move: high(candle1) < low(candle3).
  Zone = [high(candle1), low(candle3)], acts as support below price.
- Bearish FVG forms in a down-move: low(candle1) > high(candle3).
  Zone = [high(candle3), low(candle1)], acts as resistance above price.

Note: the original video-extraction docs had these two labels swapped;
this module uses the standard convention.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FVG:
    direction: str            # 'bullish' | 'bearish'
    bottom: float             # zone low
    top: float                # zone high
    formed_idx: int           # bar index of candle 3 (bar that confirms the gap)
    source: str = "fvg"       # 'fvg' | 'bpr'
    mitigated: bool = False   # price has traded back into the zone
    inverted: bool = False    # price closed through the far side of the zone
    inverted_idx: Optional[int] = None
    consumed: bool = False    # a trade was already taken off this zone

    @property
    def alive(self) -> bool:
        return not self.inverted and not self.consumed

    def contains(self, high: float, low: float) -> bool:
        """True if a bar's range intersects the zone."""
        return high >= self.bottom and low <= self.top


def fvg_at(highs, lows, i: int) -> Optional[FVG]:
    """Return the FVG confirmed by bar ``i`` (candles i-2, i-1, i), or None."""
    if i < 2:
        return None
    if highs[i - 2] < lows[i]:
        return FVG("bullish", float(highs[i - 2]), float(lows[i]), i)
    if lows[i - 2] > highs[i]:
        return FVG("bearish", float(highs[i]), float(lows[i - 2]), i)
    return None


def update_lifecycle(fvg: FVG, high: float, low: float, close: float, idx: int) -> bool:
    """Update one FVG's state against a completed bar.

    Returns True if the FVG became inverted on this bar (the inversion event).
    """
    if fvg.inverted or idx <= fvg.formed_idx:
        return False
    if fvg.direction == "bullish":
        if low <= fvg.top:
            fvg.mitigated = True
        if close < fvg.bottom:
            fvg.inverted = True
            fvg.inverted_idx = idx
            return True
    else:
        if high >= fvg.bottom:
            fvg.mitigated = True
        if close > fvg.top:
            fvg.inverted = True
            fvg.inverted_idx = idx
            return True
    return False
