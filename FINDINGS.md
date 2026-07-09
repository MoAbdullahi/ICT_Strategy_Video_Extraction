# Final Synthesis: The Reality of Mechanical ICT Strategies

A data-driven synthesis of the research journey in this repository: from a
video claiming a $936,000 prop-firm payout to a rigorously tested algorithmic
system. Every number below comes from the committed trade logs in
[`results/`](results/) and is reproducible with the commands in the
[README](README.md).

## 1. The "universal edge" fallacy

The most significant finding of the final research phase (v3) was the failure
of the `--refined` configuration to hold up across currency pairs. Identical
parameters, ~2.8 years of Yahoo Finance data each:

| Pair | Trades | Win % | Total R | PF | Max DD |
|------|-------:|------:|--------:|---:|-------:|
| EURUSD | 102 | 40.2 | +1.35 | 1.02 | −8.5% |
| GBPUSD | 114 | 43.0 | +0.81 | 1.01 | −13.5% |
| USDJPY | 86 | 40.7 | +0.52 | 1.01 | −11.0% |
| AUDUSD | 92 | 34.8 | **−19.27** | **0.68** | −27.1% |

**Conclusion:** the strategy does not possess a universal institutional edge.
Performance is pair-dependent and, in most cases, indistinguishable from a
coin flip. The AUDUSD result shows the danger of assuming success on one pair
transfers to its correlated neighbors.

## 2. Evaluation of the proposed upgrades

Two external optimization reviews proposed ten enhancements across v2 and v3.
All ten were implemented and ablation-tested. The scoreboard:

| Upgrade | Verdict | Evidence |
|---------|---------|----------|
| FVG quality scoring | **kept** (in `--refined`) | +4.7R vs baseline, stable halves |
| Partial targets + breakeven | **kept** (in `--refined`) | max DD −15.5% → −8.5%, win rate → 40% |
| DXY SMT divergence | **promising, opt-in** | PF 1.21 (EURUSD) / 1.29 (USDJPY), halves DD; but hurt GBPUSD, and DXY hourly data only covers 2024-02 onward |
| Killzone hours | rejected | −0.5R vs baseline; the "profitable hours" flip sign across sample halves |
| Displacement CISD | rejected | −8.8R vs baseline — later entries, effectively wider stops |
| Day-of-week filter | rejected | mined from the backtest's own output; textbook overfitting |
| News avoidance | implemented, untested | needs a user-supplied calendar; no free reliable source |
| Power of 3 (PO3) | rejected | −0.07R on refined, −3.32R alone, sign-flipping halves |
| Dynamic quality sizing | rejected | same R stats, worse equity (+0.5% → −4.4%) — amplifies variance without adding expectancy |
| Meta-labeling (Random Forest) | **clean null** | CV AUC 0.394 (worse than coin flip); the gatekeeper's confident picks lost −1.37R vs +2.79R unfiltered |

Walk-forward *parameter re-optimization* was deliberately not performed: with
~50 trades per year per pair, yearly re-fits select on sampling noise and
manufacture an impressive-looking equity curve out of the same coin flip.

## 3. The evolution of the strategy

1. **Baseline (faithful video implementation):** a coin flip — PF 0.98,
   before fees and slippage, which would make it a reliable loser live.
2. **Refined (v2, surviving mechanical filters):** a better-behaved coin
   flip — PF 1.02 with half the drawdown, still no demonstrated edge.
3. **Advanced (v3, contextual filters):** even the best a-priori filter
   (SMT) is highly sensitive to the asset and the data window; the ML
   gatekeeper found nothing to learn.

The $936k payout claimed in the source video is not reproduced by the rules
as stated. Whatever edge the trader has — if any — lives in discretionary
decisions the video never specifies, exactly as the
[honest complexity report](docs/video_extraction/Honest%20Implementation%20Complexity%20Report_%20ICT%20Trading%20Strategy%20in%20Python.md)
predicted before a single line of the engine was written.

## 4. Recommendations for future research

- **Higher-fidelity data.** Yahoo Finance caps hourly history at ~2–3 years
  and 15-minute history at ~60 days, and its DXY intraday feed starts
  2024-02. Futures data (ES/NQ) with longer intraday history would allow the
  video's actual market and its 15-minute layer to be tested.
- **Larger samples.** ~100 trades per configuration cannot separate a small
  real edge (PF 1.1–1.2) from noise. Ten or more years of intraday data —
  several hundred trades — is the minimum to promote SMT from "promising"
  to "demonstrated" or kill it.
- **Broader intermarket work.** SMT was the only filter with signal. Test it
  against a basket (DXY, yields, correlated pairs), with intraday timing
  finer than 1H, before trusting it with risk.

## 5. Postscript: the ES/NQ futures test

The video's trader operates in index futures, so `--refined` was run on ES=F
and NQ=F (Yahoo hourly history: 2024-02 → 2026-07), with each contract using
the other as its SMT pair (`--smt-same`, the classic ICT ES/NQ divergence):

| Configuration | Trades | Win % | Total R | PF | Max DD | Halves R |
|---------------|-------:|------:|--------:|---:|-------:|---------:|
| ES refined | 67 | 46.3 | +8.51 | 1.24 | −10.9% | +6.3 / +2.2 |
| ES refined + SMT(NQ) | 37 | 51.4 | +5.74 | 1.32 | −4.6% | +7.2 / −1.5 |
| NQ refined | 69 | 44.9 | +10.39 | 1.27 | −6.1% | +7.3 / +3.1 |
| NQ refined + SMT(ES) | 33 | 36.4 | +0.40 | 1.02 | −4.4% | +1.2 / −0.8 |

At face value the futures baselines finally look like an edge (PF ~1.25,
positive in both halves). The direction breakdown says otherwise:

- ES: longs +11.5R over 55 trades, shorts **−3.0R** over 12
- NQ: longs +13.2R over 50 trades, shorts **−2.8R** over 19

All of the profit is long-side, earned during 2024–2026 — a strong equity
bull market in which *any* long-biased entry with 2–3R targets did well.
This is directional beta, not evidence the ICT mechanics add alpha; the
video's own trade (a short) belongs to the losing side of the table. And the
SMT filter is again inconsistent: it improved ES's ratios (PF 1.32, drawdown
halved, but negative second half) while gutting NQ (+10.4R → +0.4R). A bear
or sideways regime in the data would be needed to separate strategy from
market — which loops back to the same conclusion as section 4: longer
history, which Yahoo cannot provide.

## 6. Bottom line

This repository is a research platform, not a trading system. Its honest,
reproducible answer to the original video is: **the mechanical rules, as
stated, carry no demonstrated edge** — and every "optimization" that sounded
plausible either failed testing or awaits more data. That reality check is
the deliverable.
