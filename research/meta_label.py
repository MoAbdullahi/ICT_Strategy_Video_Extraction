"""Meta-labeling study: can an ML gatekeeper predict which signals win?

Trains a Random Forest on features observable at entry time (ATR, RSI,
distance from the daily open, FVG quality, hour, weekday, direction) to
predict trade outcome, using the strategy's own trade log as labels.

Methodology notes (read before trusting any number):
- ~100 trades is a very small sample for ML. Results are reported with a
  chronological holdout AND time-series cross-validation; anything within
  a few points of the base rate is noise.
- The gatekeeper simulation applies the trained model only to the untouched
  holdout segment — no test-set leakage into training.

Usage:
    python research/meta_label.py [--symbol EURUSD=X]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ict.data import fetch                      # noqa: E402
from ict.indicators import atr as atr_ind, rsi as rsi_ind   # noqa: E402
from ict.strategy import Params, run_strategy   # noqa: E402


def build_dataset(symbol: str) -> pd.DataFrame:
    daily = fetch(symbol, "1d", "5y")
    h1 = fetch(symbol, "1h", "730d")
    trades = run_strategy(daily, h1, Params(min_fvg_quality=0.5, partial_targets=True))
    if trades.empty:
        raise SystemExit("No trades to learn from.")

    closes = h1["close"].to_numpy()
    a = atr_ind(h1["high"].to_numpy(), h1["low"].to_numpy(), closes)
    r = rsi_ind(closes)
    dates = pd.Series([ts.date() for ts in h1.index], index=h1.index)
    day_open = h1["open"].groupby(dates).transform("first").to_numpy()

    pos = h1.index.get_indexer(pd.DatetimeIndex(trades["entry_time"]))
    assert (pos >= 0).all(), "every entry_time must be an h1 bar"
    feats = pd.DataFrame({
        "atr_norm": a[pos] / closes[pos],
        "rsi": r[pos],
        "dist_open_atr": (closes[pos] - day_open[pos]) / a[pos],
        "quality": trades["quality"].to_numpy(),
        "hour": [ts.hour for ts in trades["entry_time"]],
        "dow": [ts.weekday() for ts in trades["entry_time"]],
        "is_long": (trades["direction"] == "long").astype(int).to_numpy(),
    })
    feats["win"] = (trades["r"] > 0).astype(int).to_numpy()
    feats["r"] = trades["r"].to_numpy()
    feats["entry_time"] = trades["entry_time"].to_numpy()
    return feats.sort_values("entry_time").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD=X")
    args = ap.parse_args()

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score

    df = build_dataset(args.symbol)
    X = df[["atr_norm", "rsi", "dist_open_atr", "quality", "hour", "dow", "is_long"]]
    y = df["win"]
    n = len(df)
    base_rate = y.mean()
    print(f"{args.symbol}: {n} trades, base win rate {base_rate:.1%}")

    model = RandomForestClassifier(n_estimators=300, max_depth=3,
                                   min_samples_leaf=5, random_state=0)

    # time-series cross-validated AUC (0.5 = no skill)
    cv = TimeSeriesSplit(n_splits=4)
    aucs = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
    print(f"TimeSeries CV AUC: {aucs.mean():.3f} +/- {aucs.std():.3f}  (folds: "
          + ", ".join(f"{a:.2f}" for a in aucs) + ")")

    # chronological 60/40 holdout + gatekeeper simulation
    split = int(n * 0.6)
    model.fit(X.iloc[:split], y.iloc[:split])
    proba = model.predict_proba(X.iloc[split:])[:, 1]
    hold = df.iloc[split:]
    auc = roc_auc_score(y.iloc[split:], proba) if y.iloc[split:].nunique() > 1 else float("nan")
    print(f"Holdout ({n - split} trades) AUC: {auc:.3f}")

    taken = hold[proba >= 0.5]
    print(f"Gatekeeper (p>=0.5): takes {len(taken)}/{len(hold)} holdout trades, "
          f"total R {taken['r'].sum():+.2f} vs unfiltered {hold['r'].sum():+.2f}")

    imp = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("Feature importances:", ", ".join(f"{k}={v:.2f}" for k, v in imp.items()))


if __name__ == "__main__":
    main()
