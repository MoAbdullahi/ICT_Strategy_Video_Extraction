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

## Quick start

```bash
pip install -r requirements.txt

# run the backtest (downloads EURUSD daily + 1H data from Yahoo, cached in data/)
python run_backtest.py

# any Yahoo ticker works
python run_backtest.py --symbol ES=F
python run_backtest.py --symbol "EURUSD=X" --no-cache   # force fresh download

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
│   ├── fvg.py                 <- Fair Value Gap detection & lifecycle
│   ├── bpr.py                 <- Balanced Price Range (overlapping FVGs)
│   ├── structure.py           <- swing points & CISD (structure breaks)
│   ├── strategy.py            <- walk-forward multi-timeframe engine
│   └── backtest.py            <- equity curve & statistics
├── tests/
│   └── test_ict.py            <- unit tests for the detection primitives
├── results/
│   └── trades_EURUSD_X.csv    <- trade log from the default run
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
