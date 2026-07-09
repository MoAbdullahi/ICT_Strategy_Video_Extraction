# ICT Strategy — Video Extraction & Backtest

A faithful, fully-testable Python implementation of the ICT (Inner Circle
Trader) multi-timeframe strategy described in a trading video, backtested on
free Yahoo Finance data.

**The pipeline this repo documents:** a strategy video was extracted and
transcribed → the rules were formalized into precise mathematical logic → the
logic was implemented as a walk-forward backtest → the claims were tested on
real data.

## The strategy in one paragraph

Establish bias on the **daily** chart: wait for price to trade into an
unmitigated daily **Fair Value Gap** (or **Balanced Price Range**). Then drop
to the **1-hour** chart and wait for two confirmations: an **inversion of the
latest 1H FVG** and a **Change In State of Delivery** (a close through the
latest confirmed swing). Enter on the confirming close, stop beyond the high/
low of the move, and target resting **liquidity** at recent internal swing
levels for 2–4R. Full rules, parameters, and deviations from the video are in
[STRATEGY.md](STRATEGY.md).

## Backtest results (spoiler: the video's edge doesn't replicate)

Default run — `EURUSD=X`, daily bias + 1H confirmation, Yahoo Finance data,
2023-09 → 2026-07, 1% risk per trade:

```
====================================================
  ICT Strategy Backtest Results
====================================================
  Period            : 2023-09-25 -> 2026-07-06
  Trades            : 105  (32 wins / 73 losses)
  Win rate          : 30.5%
  Total R           : -1.24
  Average R / trade : -0.01
  Best / worst R    : +3.00 / -1.00
  Profit factor     : 0.98
  Avg bars held     : 66 (1H bars)
----------------------------------------------------
  Equity (1% risk)  : 10,000 -> 9,754.40
  Net return        : -2.46%
  Max drawdown      : -15.52%
====================================================
```

**Honest takeaway:** implemented mechanically, over ~2.8 years the setup is a
coin flip (profit factor 0.98) — the 2–3R winners at a ~30% win rate roughly
pay for the losers and nothing more. The $936k payout in the source video is
not reproduced by the rules as stated; whatever edge exists lives in the
discretionary zone selection the trader never specifies. This is exactly the
conclusion anticipated by the
[honest complexity report](docs/video_extraction/Honest%20Implementation%20Complexity%20Report_%20ICT%20Trading%20Strategy%20in%20Python.md)
produced during extraction. The full trade log is in
[`results/trades_EURUSD_X.csv`](results/trades_EURUSD_X.csv).

## v2: optimization review, ablation-tested

An external optimization report proposed six enhancements (killzone filtering,
day-of-week filtering, news avoidance, FVG quality scoring, displacement-based
CISD, and partial profit-taking). All six are now implemented as configurable
parameters — and each was **ablation-tested** instead of taken on faith.
Same data, same period, one change at a time:

| Configuration | Trades | Win % | Total R | PF | Return | Max DD |
|---------------|-------:|------:|--------:|---:|-------:|-------:|
| baseline (v1) | 105 | 30.5 | −1.24 | 0.98 | −2.5% | −15.5% |
| killzones 7–10, 12–15 UTC | 96 | 30.2 | −1.71 | 0.97 | −2.8% | −13.1% |
| FVG quality ≥ 0.5 | 101 | 31.7 | **+3.50** | **1.05** | +2.3% | −13.2% |
| CISD displacement ≥ 0.5 ATR | 99 | 27.3 | −10.02 | 0.86 | −10.5% | −15.6% |
| partial targets | 105 | 41.0 | +0.69 | 1.01 | −0.2% | **−10.1%** |
| **quality 0.5 + partials (`--refined`)** | 102 | 40.2 | **+1.35** | 1.02 | **+0.5%** | **−8.5%** |
| everything combined | 97 | 37.1 | −8.26 | 0.86 | −8.7% | −12.3% |

What survived testing:

- **FVG quality scoring** (displacement body ≥ 0.5 × ATR) — the only change
  that improved expectancy, and the `--refined` combo is positive in *both*
  chronological halves of the data (+0.88R / +0.47R). Still statistically
  indistinguishable from breakeven at ~100 trades.
- **Partial targets** — don't add expectancy but nearly halve the max
  drawdown (−15.5% → −8.5%) and lift the win rate to ~40%.

What did **not** survive:

- **Killzones** made results *worse*. The report's "profitable hours" (07:00,
  11:00–12:00 UTC) flip sign between the first and second half of the sample —
  and its own table shows 08:00 and 13:00–14:00, inside the proposed
  killzones, are net losers. Classic in-sample pattern mining.
- **Displacement CISD** cost −8.8R vs baseline: requiring a big-bodied
  breaking candle makes entries later and stops effectively wider.
- **Day-of-week filtering** (Tuesday good, Wednesday bad) is derived from the
  backtest's own output. It's implemented (`--days`) but off by default and
  labeled what it is: curve fitting.
- **Stricter quality (≥ 1.0)** degrades again (PF 0.92, wildly unstable
  halves) — the 0.5 reading is not a tunable edge, it's a coarse noise filter.

**Bottom line:** honest filtering turns a coin flip into a slightly
better-behaved coin flip (PF 1.02, half the drawdown). No configuration tested
here turns the video's strategy into a demonstrated edge, and the "optimized"
combination of *all* proposed filters loses more than the baseline.

Reproduce with `python run_backtest.py --refined`
(trade log: [`results/trades_EURUSD_X_refined.csv`](results/trades_EURUSD_X_refined.csv)).

## v3: cross-asset validation, SMT, PO3, and meta-labeling

A second review round proposed "next generation" upgrades. Same protocol:
implement everything, test everything, report what actually happened.

### The ultimate test first: same parameters, other pairs

`--refined` run unchanged on correlated majors (~2.8y each):

| Pair | Trades | Win % | Total R | PF | Max DD |
|------|-------:|------:|--------:|---:|-------:|
| EURUSD | 102 | 40.2 | +1.35 | 1.02 | −8.5% |
| GBPUSD | 114 | 43.0 | +0.81 | 1.01 | −13.5% |
| USDJPY | 86 | 40.7 | +0.52 | 1.01 | −11.0% |
| AUDUSD | 92 | 34.8 | **−19.27** | **0.68** | −27.1% |

**Verdict: no universal edge.** Three pairs cluster at breakeven (PF ≈ 1.01)
and AUDUSD loses heavily. A real institutional edge doesn't pick which
correlated majors it works on.

### DXY SMT divergence — the most interesting result so far

Requiring SMT divergence vs the Dollar Index (`--smt DX-Y.NYB`) before entry
(the pair sweeps a swing extreme, DXY fails to confirm):

| Configuration | Trades | Win % | Total R | PF | Max DD | Halves R |
|---------------|-------:|------:|--------:|---:|-------:|---------:|
| EURUSD refined + SMT | 54 | 46.3 | +6.03 | 1.21 | −4.9% | +2.1 / +4.0 |
| USDJPY refined + SMT | 56 | 48.2 | +8.06 | 1.29 | −6.1% | −0.2 / +8.3 |
| AUDUSD refined + SMT | 56 | 42.9 | −2.80 | 0.91 | −11.9% | (was −19.3 without) |
| GBPUSD refined + SMT | 61 | 37.7 | −7.10 | 0.81 | −13.6% | (was +0.8 without) |

Two important honesty caveats. First, Yahoo's DXY hourly history starts
2024-02, so SMT runs cover a shorter window — refined alone earns +3.44R on
EURUSD in that same window, meaning SMT's true increment there is ~+2.6R, not
+6. Second, the cross-pair picture is mixed: it substantially helps EURUSD,
USDJPY and AUDUSD but hurts GBPUSD. SMT halves the trade count and cuts
drawdowns everywhere, is grounded in an a-priori ICT concept rather than mined
from this data, and is the only filter tested that produced PF > 1.2 on two
pairs — but it is **not yet a demonstrated edge**. It ships as an opt-in flag,
not as part of `--refined`.

### What didn't work (tested, EURUSD)

| Proposal | Result | Why it fails |
|----------|--------|--------------|
| Power of 3 (`--po3`) | refined +PO3: −0.07R (PF 1.00); alone: −3.32R, sign-flipping halves | the daily-open manipulation check mostly removes random trades |
| Dynamic sizing (`--dynamic-risk`) | same R stats, return +0.5% → −4.4%, DD −8.5% → −13.6% | FVG quality doesn't predict outcome beyond the 0.5 threshold, so sizing up on it just amplifies variance |
| Meta-labeling (`research/meta_label.py`) | **CV AUC 0.394 ± 0.03** (0.5 = coin flip); the p≥0.5 gatekeeper keeps 6/41 holdout trades worth −1.37R vs +2.79R unfiltered | 102 trades cannot train a 7-feature classifier; the forest memorizes noise, and its confident picks are anti-predictive |

### Why there is no walk-forward *parameter* optimization here

The review also proposed rolling re-optimization (fit parameters on year 1,
trade year 2). With ~50 trades per year per pair, every parameter choice a
yearly re-fit makes is dominated by sampling noise — it would manufacture an
impressive-looking curve out of the same coin flip. The validation used
instead: fixed parameters everywhere, chronological-halves stability checks,
and zero-refit transfer to three other pairs (above). That's the test the
strategy keeps failing.

## Quick start

```bash
pip install -r requirements.txt

# run the backtest (downloads EURUSD daily + 1H data from Yahoo, cached in data/)
python run_backtest.py

# best-behaved configuration found (FVG quality + partial targets)
python run_backtest.py --refined

# any Yahoo ticker works; filters are opt-in flags
python run_backtest.py --symbol ES=F
python run_backtest.py --refined --smt DX-Y.NYB          # + DXY SMT divergence
python run_backtest.py --killzones "7-10,12-15" --days Mon,Tue,Thu --po3
python run_backtest.py --symbol "EURUSD=X" --no-cache   # force fresh download

# meta-labeling research study (requires scikit-learn)
python research/meta_label.py

# run the unit tests
python -m unittest discover -s tests
```

## Repository layout

```
├── README.md                  <- you are here
├── STRATEGY.md                <- exact strategy rules & parameters
├── run_backtest.py            <- CLI entry point
├── requirements.txt
├── ict/
│   ├── data.py                <- Yahoo Finance download + CSV cache
│   ├── fvg.py                 <- Fair Value Gap detection, lifecycle & quality
│   ├── bpr.py                 <- Balanced Price Range (overlapping FVGs)
│   ├── structure.py           <- swing points & CISD (structure breaks)
│   ├── indicators.py          <- ATR & RSI (displacement / research features)
│   ├── strategy.py            <- walk-forward multi-timeframe engine + filters
│   └── backtest.py            <- equity curve & statistics
├── research/
│   └── meta_label.py          <- ML gatekeeper study (honest null result)
├── tests/
│   └── test_ict.py            <- unit tests for the detection primitives
├── results/
│   ├── trades_EURUSD_X.csv           <- trade log, baseline run
│   └── trades_EURUSD_X_refined.csv   <- trade log, --refined run
└── docs/video_extraction/     <- original video transcript & analysis docs
    ├── ...transcription....txt
    ├── Trading Strategy Analysis_ Max Anthony's ICT Concepts.md
    ├── Precise Mathematical Logic for ICT Trading Strategy Components.md
    ├── Honest Implementation Complexity Report_ ....md
    ├── extract_fb_video.py    <- helper used to pull the video URL
    └── ict_strategy_implementation.py  <- original skeleton (superseded by ict/)
```

## Design notes

- **No lookahead.** Swings confirm N bars after the pivot, daily zones only
  activate the day after the candle completes, and every decision uses
  completed bars only.
- **Conservative fills.** If a bar touches both stop and target, the stop is
  assumed to be hit first.
- **No curve fitting.** Parameters are the natural readings of the video's
  rules (N=2 fractals, 2–4R targets, ~1–2 day bias windows); the reported
  result is the first honest run, not an optimized one.
- **Yahoo data limits.** 1H history is capped (~2–3 years) and 15m history at
  ~60 days, which is why the video's 15-minute layer is omitted.

## Disclaimer

Educational project. Nothing here is financial advice; the backtest itself
shows the mechanical rules carry no demonstrated edge. Do not trade real
money based on this repository.
