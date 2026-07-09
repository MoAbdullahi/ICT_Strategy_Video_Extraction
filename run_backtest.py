"""Run the ICT multi-timeframe strategy backtest on Yahoo Finance data.

Usage:
    python run_backtest.py                       # EURUSD=X, defaults
    python run_backtest.py --symbol ES=F
    python run_backtest.py --no-cache            # force fresh Yahoo download
"""

import argparse
from pathlib import Path

from ict.backtest import compute_stats, format_stats
from ict.data import fetch
from ict.strategy import Params, run_strategy

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main():
    ap = argparse.ArgumentParser(description="ICT strategy backtest (Yahoo Finance data)")
    ap.add_argument("--symbol", default="EURUSD=X", help="Yahoo ticker (default: EURUSD=X)")
    ap.add_argument("--h1-period", default="730d", help="1H history window (Yahoo max: 730d)")
    ap.add_argument("--daily-period", default="5y", help="Daily history window")
    ap.add_argument("--no-cache", action="store_true", help="Ignore the local CSV cache")
    args = ap.parse_args()

    print(f"Fetching {args.symbol}: daily ({args.daily_period}) + 1H ({args.h1_period}) from Yahoo Finance...")
    daily = fetch(args.symbol, "1d", args.daily_period, use_cache=not args.no_cache)
    h1 = fetch(args.symbol, "1h", args.h1_period, use_cache=not args.no_cache)
    print(f"  daily bars: {len(daily)}   1H bars: {len(h1)}"
          f"   ({h1.index[0]:%Y-%m-%d} -> {h1.index[-1]:%Y-%m-%d})")

    params = Params()
    trades = run_strategy(daily, h1, params)
    stats = compute_stats(trades, risk_pct=params.risk_pct)
    print()
    print(format_stats(stats))

    if not trades.empty:
        RESULTS_DIR.mkdir(exist_ok=True)
        safe = args.symbol.replace("=", "_").replace("/", "_").replace("^", "_")
        out = RESULTS_DIR / f"trades_{safe}.csv"
        trades.to_csv(out, index=False)
        print(f"\nTrade log written to {out}")


if __name__ == "__main__":
    main()
