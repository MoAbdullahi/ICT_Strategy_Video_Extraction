"""Small indicator helpers (walk-forward safe)."""

import numpy as np


def atr(highs, lows, closes, n: int = 14) -> np.ndarray:
    """Average True Range as a rolling simple mean of True Range.

    atr[i] uses bars up to and including bar i, so it is safe to read at
    the close of bar i. Early bars (before ``n`` samples) fall back to the
    expanding mean; atr[0] is the first bar's range.
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    prev_close = np.concatenate([[closes[0]], closes[:-1]])
    tr = np.maximum(highs - lows,
                    np.maximum(np.abs(highs - prev_close),
                               np.abs(lows - prev_close)))
    out = np.empty_like(tr)
    csum = np.cumsum(tr)
    for i in range(len(tr)):
        if i < n:
            out[i] = csum[i] / (i + 1)
        else:
            out[i] = (csum[i] - csum[i - n]) / n
    return out
