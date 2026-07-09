# ICT Multi-Timeframe Strategy — Full Rules

This document defines the exact, testable rules implemented in this repository.
The strategy was extracted from a video in which trader "Dhesi" describes the
setup behind a $936,000 Apex prop-firm payout. The original transcript and
analysis documents are preserved in [`docs/video_extraction/`](docs/video_extraction/).

The video describes only the short side. This implementation trades both
directions symmetrically; the short side is described below and the long side
is the exact mirror image.

---

## Concepts

### Fair Value Gap (FVG)

A three-candle imbalance in price delivery.

| Type | Condition | Zone | Role |
|------|-----------|------|------|
| **Bullish FVG** (forms in an up-move) | `high(C1) < low(C3)` | `[high(C1), low(C3)]` | support below price |
| **Bearish FVG** (forms in a down-move) | `low(C1) > high(C3)` | `[high(C3), low(C1)]` | resistance above price |

> Note: the original extraction documents had these two labels swapped.
> This implementation uses the standard ICT convention above.

**Lifecycle.** An FVG is *mitigated* when price trades back into the zone,
and *inverted* when a candle **closes through the far side** of the zone.
An inverted FVG flips its role (broken support becomes resistance).

### Balanced Price Range (BPR)

The overlap of a bullish and a bearish FVG that formed within
`daily_bpr_max_age` bars of each other. The BPR takes the direction of the
**later** FVG and its zone is the intersection of the two gaps. Treated as a
stronger version of an FVG zone.

### Swing points and liquidity

A **swing high/low** is a fractal pivot: a bar whose high (low) exceeds the
highs (lows) of `N = 2` bars on each side. A pivot is only *confirmed* `N`
bars after it forms (no lookahead). **Sell-side liquidity** rests below
confirmed swing lows ("internal lows"); buy-side liquidity above swing highs.

### Change In State of Delivery (CISD)

A close through the most recent unbroken confirmed swing:
close below the latest swing low = **bearish CISD**;
close above the latest swing high = **bullish CISD**.
Each swing level can fire at most once.

---

## The Setup (short side)

### 1. Daily bias — "wait for the move into the daily gap"

- Detect all FVGs and BPRs on the **daily** chart. A zone only becomes
  usable the day *after* its third candle completes.
- When a 1-hour bar **taps** a live (un-inverted, unused) daily **bearish**
  zone — bar range intersects the zone — a **bearish bias** is armed.
- The bias stays armed for `bias_window = 48` 1H bars (re-armed while price
  remains in the zone), and is cancelled if the daily zone inverts
  (1H close above the zone top).

### 2. One-hour confirmation — both required while the bias is armed

1. **FVG inversion** — a recent bullish 1H FVG (formed no earlier than
   `h1_fvg_max_age = 24` bars before the bias opened) is **closed through
   downward**. This is the "inversion of the latest fair value gap".
2. **Bearish CISD** — a 1H close below the latest confirmed 1H swing low
   ("broke structure to the downside").

They may complete in either order; entry triggers on the bar that completes
the second condition.

### 3. Entry, stop, target

| Element | Rule |
|---------|------|
| **Entry** | Short at the close of the confirming 1H bar |
| **Stop** | Above the high of the move: `max(high, last 24 bars) × (1 + 0.0002)` |
| **Target** | Nearest confirmed 1H swing low below entry (resting sell-side liquidity, scanned over the last 200 bars) that offers **≥ 2R**; if none qualifies, a fixed **3R** target |
| **Time exit** | Position closed at market after `max_hold = 240` 1H bars |
| **Stop/target conflict** | If one bar touches both, the stop is assumed hit first (conservative) |

### 4. Risk management

- **1% of equity risked per trade** (fixed fractional).
- One position at a time; a daily zone is consumed after producing a trade.
- Results are tracked in **R-multiples** (risk units), matching the video's
  "3 to 4 R" framing.

---

## Parameters

All parameters live in `ict/strategy.py::Params`:

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `swing_n` | 2 | fractal width for swing points |
| `bias_window` | 48 | 1H bars a bias stays armed after a zone tap |
| `h1_fvg_max_age` | 24 | recency requirement for the inverted 1H FVG |
| `stop_lookback` | 24 | bars defining the protective high/low of the move |
| `stop_buffer` | 0.0002 | fractional buffer beyond the stop level |
| `target_lookback` | 200 | scan window for liquidity targets |
| `min_rr` | 2.0 | minimum R offered by a liquidity target |
| `fallback_rr` | 3.0 | fixed-R target when no liquidity qualifies |
| `max_hold` | 240 | 1H bars before time exit |
| `risk_pct` | 0.01 | equity fraction risked per trade |
| `daily_bpr_max_age` | 30 | max daily bars between FVGs forming a BPR |

---

## Deviations from the video

| Video | This implementation | Why |
|-------|--------------------|-----|
| 15-minute refinement layer | Omitted — confirmation on 1H only | Yahoo Finance limits 15m history to ~60 days, too little to backtest |
| Discretionary zone selection ("marked out at these lows") | Every detected zone is eligible | An algorithm cannot replicate unstated discretion; see the honest complexity report in `docs/` |
| Short-only example | Symmetric long/short | The logic is direction-agnostic |
| Futures (ES/NQ via Apex) | EURUSD (`EURUSD=X`) by default | Chosen by the repo owner; any Yahoo ticker works via `--symbol` |

## No-lookahead guarantees

- Swings confirm `N` bars after the pivot.
- Daily zones activate only after the daily candle completes (next day).
- FVG lifecycle, CISD, bias and entries all use completed bars only.
- Entries execute at the close of the signal bar; exits on later bars.
