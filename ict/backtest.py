"""Backtest accounting: equity curve and performance statistics."""

from typing import Optional

import pandas as pd


def compute_stats(trades: pd.DataFrame, risk_pct: float = 0.01,
                  starting_equity: float = 10_000.0,
                  dynamic_risk: bool = False) -> Optional[dict]:
    """Compute performance stats from the trade list (fixed fractional risk).

    ``dynamic_risk`` scales each trade's risk by its FVG quality score,
    clipped to [0.5, 1.5] x ``risk_pct``. R-based stats are unaffected —
    only the equity curve, return, and drawdown change.
    """
    if trades.empty:
        return None

    trades = trades.sort_values("exit_time").reset_index(drop=True)
    equity = starting_equity
    curve = [equity]
    qualities = trades["quality"] if "quality" in trades else pd.Series(1.0, index=trades.index)
    for r, q in zip(trades["r"], qualities):
        scale = min(1.5, max(0.5, float(q))) if dynamic_risk else 1.0
        equity *= 1 + risk_pct * scale * r
        curve.append(equity)
    curve = pd.Series(curve)

    peak = curve.cummax()
    max_dd = ((curve - peak) / peak).min()

    r = trades["r"]
    wins = r[r > 0]
    losses = r[r <= 0]
    gross_win = wins.sum()
    gross_loss = -losses.sum()

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades),
        "total_r": r.sum(),
        "avg_r": r.mean(),
        "best_r": r.max(),
        "worst_r": r.min(),
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else float("inf"),
        "starting_equity": starting_equity,
        "final_equity": float(curve.iloc[-1]),
        "return_pct": float(curve.iloc[-1] / starting_equity - 1),
        "max_drawdown_pct": float(max_dd),
        "avg_bars_held": trades["bars_held"].mean(),
        "first_trade": trades["entry_time"].iloc[0],
        "last_trade": trades["exit_time"].iloc[-1],
    }


def format_stats(stats: Optional[dict]) -> str:
    if stats is None:
        return "No trades were generated."
    lines = [
        "=" * 52,
        "  ICT Strategy Backtest Results",
        "=" * 52,
        f"  Period            : {stats['first_trade']:%Y-%m-%d} -> {stats['last_trade']:%Y-%m-%d}",
        f"  Trades            : {stats['trades']}  ({stats['wins']} wins / {stats['losses']} losses)",
        f"  Win rate          : {stats['win_rate']:.1%}",
        f"  Total R           : {stats['total_r']:+.2f}",
        f"  Average R / trade : {stats['avg_r']:+.2f}",
        f"  Best / worst R    : {stats['best_r']:+.2f} / {stats['worst_r']:+.2f}",
        f"  Profit factor     : {stats['profit_factor']:.2f}",
        f"  Avg bars held     : {stats['avg_bars_held']:.0f} (1H bars)",
        "-" * 52,
        f"  Equity (1% risk)  : {stats['starting_equity']:,.0f} -> {stats['final_equity']:,.2f}",
        f"  Net return        : {stats['return_pct']:+.2%}",
        f"  Max drawdown      : {stats['max_drawdown_pct']:.2%}",
        "=" * 52,
    ]
    return "\n".join(lines)
