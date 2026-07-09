"""Balanced Price Range (BPR): the overlap of a bullish and a bearish FVG.

The BPR takes the direction of the *later* FVG — e.g. a bearish FVG that
overlaps an earlier bullish FVG creates a bearish BPR (resistance).
"""

from typing import List, Optional

from .fvg import FVG


def bpr_from(existing: List[FVG], new_fvg: FVG, max_age: int) -> Optional[FVG]:
    """Return a BPR zone if ``new_fvg`` overlaps a recent opposing FVG."""
    for f in reversed(existing):
        if f.direction == new_fvg.direction or f.inverted:
            continue
        if new_fvg.formed_idx - f.formed_idx > max_age:
            break
        lo = max(f.bottom, new_fvg.bottom)
        hi = min(f.top, new_fvg.top)
        if lo < hi:
            return FVG(
                direction=new_fvg.direction,
                bottom=lo,
                top=hi,
                formed_idx=new_fvg.formed_idx,
                source="bpr",
            )
    return None
