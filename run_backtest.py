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
    ap.add_argument("--killzones", default=None,
                    help='UTC hour windows for entries, e.g. "7-10,12-15" (default: off)')
    ap.add_argument("--days", default=None,
                    help='Allowed entry weekdays, e.g. "Mon,Tue,Thu" (in-sample-derived filter; default: off)')
    ap.add_argument("--news-csv", default=None,
                    help="CSV with a 'time' column of UTC timestamps of high-impact news to avoid")
    ap.add_argument("--quality", type=float, default=0.0,
                    help="Min FVG displacement quality (candle body / ATR) for the inverted 1H FVG")
    ap.add_argument("--cisd-body", type=float, default=0.0,
                    help="Min CISD breaking-candle body as a multiple of ATR")
    ap.add_argument("--partials", action="store_true",
                    help="Two-stage exits: half off at nearest liquidity, stop to breakeven")
    ap.add_argument("--refined", action="store_true",
                    help="Preset: --quality 0.5 --partials (the only refinements that "
                         "survived ablation testing; see README)")
    args = ap.parse_args()

    day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    killzones = None
    if args.killzones:
        killzones = tuple(tuple(int(x) for x in w.split("-")) for w in args.killzones.split(","))
    allowed_days = None
    if args.days:
        allowed_days = tuple(day_map[d.strip().lower()[:3]] for d in args.days.split(","))
    news_times = None
    if args.news_csv:
        import pandas as pd
        news_times = list(pd.to_datetime(pd.read_csv(args.news_csv)["time"], utc=True))
    if args.refined:
        args.quality = args.quality or 0.5
        args.partials = True

    print(f"Fetching {args.symbol}: daily ({args.daily_period}) + 1H ({args.h1_period}) from Yahoo Finance...")
    daily = fetch(args.symbol, "1d", args.daily_period, use_cache=not args.no_cache)
    h1 = fetch(args.symbol, "1h", args.h1_period, use_cache=not args.no_cache)
    print(f"  daily bars: {len(daily)}   1H bars: {len(h1)}"
          f"   ({h1.index[0]:%Y-%m-%d} -> {h1.index[-1]:%Y-%m-%d})")

    params = Params(
        killzones=killzones,
        allowed_days=allowed_days,
        news_times=news_times,
        min_fvg_quality=args.quality,
        cisd_min_body_atr=args.cisd_body,
        partial_targets=args.partials,
    )
    trades = run_strategy(daily, h1, params)
    stats = compute_stats(trades, risk_pct=params.risk_pct)
    print()
    print(format_stats(stats))

    if not trades.empty:
        RESULTS_DIR.mkdir(exist_ok=True)
        safe = args.symbol.replace("=", "_").replace("/", "_").replace("^", "_")
        suffix = "_refined" if args.refined else ""
        out = RESULTS_DIR / f"trades_{safe}{suffix}.csv"
        trades.to_csv(out, index=False)
        print(f"\nTrade log written to {out}")


if __name__ == "__main__":
    main()
