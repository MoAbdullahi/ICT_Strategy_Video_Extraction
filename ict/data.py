"""Yahoo Finance data download with a local CSV cache."""

from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch(symbol: str, interval: str, period: str, use_cache: bool = True) -> pd.DataFrame:
    """Download OHLC data for ``symbol`` and return a clean DataFrame.

    Columns: open, high, low, close. Index: DatetimeIndex (tz-aware for
    intraday intervals). Cached under ``data/`` so repeated runs are offline.
    """
    DATA_DIR.mkdir(exist_ok=True)
    safe = symbol.replace("=", "_").replace("/", "_").replace("^", "_")
    cache_file = DATA_DIR / f"{safe}_{interval}_{period}.csv"

    if use_cache and cache_file.exists():
        return pd.read_csv(cache_file, index_col=0, parse_dates=True)

    df = yf.download(symbol, interval=interval, period=period, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"No data returned from Yahoo for {symbol} ({interval}, {period})")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close"]]
    df = df[~df.index.duplicated(keep="first")].sort_index().dropna()
    df.to_csv(cache_file)
    return df
