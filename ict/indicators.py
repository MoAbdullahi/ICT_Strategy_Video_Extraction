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


def rsi(closes, n: int = 14) -> np.ndarray:
    """Wilder RSI. rsi[i] uses closes up to and including bar i."""
    closes = np.asarray(closes, dtype=float)
    delta = np.diff(closes, prepend=closes[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_g = np.empty_like(gain)
    avg_l = np.empty_like(loss)
    avg_g[0], avg_l[0] = gain[0], loss[0]
    alpha = 1.0 / n
    for i in range(1, len(closes)):
        avg_g[i] = avg_g[i - 1] + alpha * (gain[i] - avg_g[i - 1])
        avg_l[i] = avg_l[i - 1] + alpha * (loss[i] - avg_l[i - 1])
    rs = np.divide(avg_g, avg_l, out=np.full_like(avg_g, np.inf), where=avg_l > 0)
    return 100.0 - 100.0 / (1.0 + rs)
