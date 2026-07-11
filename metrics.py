#!/usr/bin/env python3
"""
metrics.py — Full SPEC.md track-record metrics from per-day classification.

Consumes per_day_results.csv (emitted by backtest.py per decision 0001). Each
row is one trading day with: flag (did the signal fire?) and is_drawdown_day
(was it followed by a >=5% drawdown within 30 trading days?). With both per day,
all SPEC.md metrics are computable from a single source — no signal re-derivation.

TERMINOLOGY (SPEC.md is the contract; the dashboard sentence is colloquial):
  precision  = TP / (TP + FP)   = hits / flags
  hit_rate   = TP / (TP + FN)   = TPR  (flags among all drawdown days)
  fpr        = FP / (FP + TN)         (flags among all non-drawdown days)
  base_rate  = (TP + FN) / N           (any-day drawdown probability)
  lift       = precision / base_rate
The dashboard headline calls hits/flags the "hit rate" in plain English; in the
data model that number is `precision`. Both are reported so nothing drifts.

V1 universe is SPY only (SPEC.md). --ticker defaults to SPY; pooling tickers
would mix populations and violate the single-universe design.
"""
import argparse
import math
from pathlib import Path

import pandas as pd

DRAWDOWN_LABEL = ">5% drawdown within 30 days"


def load_per_day(path: Path, ticker: str | None) -> pd.DataFrame:
    """Load per-day CSV, optionally filtered to one ticker (V1: SPY)."""
    df = pd.read_csv(path)
    if ticker:
        df = df[df["ticker"].str.upper() == ticker.upper()].copy()
    if df.empty:
        raise ValueError(f"No per-day rows for ticker={ticker!r} in {path}")
    return df


def total_flags(df: pd.DataFrame) -> int:
    """Number of days the signal fired (TP + FP)."""
    return int((df["flag"] == 1).sum())


def hit_count(df: pd.DataFrame) -> int:
    """Flag days that were followed by a >=5% drawdown (TP)."""
    return int(((df["flag"] == 1) & (df["is_drawdown_day"] == 1)).sum())


def false_alarm_count(df: pd.DataFrame) -> int:
    """Flag days NOT followed by a >=5% drawdown (FP)."""
    return int(((df["flag"] == 1) & (df["is_drawdown_day"] == 0)).sum())


def base_rate(df: pd.DataFrame) -> float:
    """P(any given day is followed by a >=5% drawdown) = (TP+FN)/N."""
    return float((df["is_drawdown_day"] == 1).mean())


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Wilson score 95% CI for a binomial proportion (k of n).

    Why Wilson, not the normal (Wald) approximation:
      - Wald is symmetric about p_hat and can fall OUTSIDE [0, 1].
      - Wald collapses to zero width at k=0 or k=n, implying false certainty
        exactly where we have the LEAST information.
      - Wald has poor coverage for small n (<~40) or extreme p — precisely the
        regime of a rare-event signal on a short SPY history.
      - Wilson stays in [0, 1] and stays non-degenerate at the boundaries.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def precision(df: pd.DataFrame) -> tuple[float, float, float]:
    """(precision, ci_low, ci_high) = hits/flags with Wilson 95% CI."""
    n, k = total_flags(df), hit_count(df)
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    lo, hi = wilson_interval(k, n)
    return (k / n, lo, hi)


def hit_rate_tpr(df: pd.DataFrame) -> float:
    """TPR = TP / (TP + FN) = flags among all drawdown days (SPEC hit rate)."""
    dd = df[df["is_drawdown_day"] == 1]
    return float((dd["flag"] == 1).mean()) if len(dd) else float("nan")


def false_alarm_rate_fpr(df: pd.DataFrame) -> float:
    """FPR = FP / (FP + TN) = flags among all non-drawdown days (SPEC FPR)."""
    nd = df[df["is_drawdown_day"] == 0]
    return float((nd["flag"] == 1).mean()) if len(nd) else float("nan")


def lift(df: pd.DataFrame) -> float:
    """precision / base_rate. >1 means the signal beats a coin at the base rate."""
    br = base_rate(df)
    p = precision(df)[0]
    return p / br if br else float("nan")


def _hit_drawdowns(df: pd.DataFrame) -> pd.Series:
    return df.loc[(df["flag"] == 1) & (df["is_drawdown_day"] == 1), "max_drawdown_30d"]


def avg_drawdown_on_hits(df: pd.DataFrame) -> float:
    """Mean max_drawdown_30d over hits (negative number)."""
    h = _hit_drawdowns(df)
    return float(h.mean()) if len(h) else float("nan")


def median_drawdown_on_hits(df: pd.DataFrame) -> float:
    """Median max_drawdown_30d over hits (negative number)."""
    h = _hit_drawdowns(df)
    return float(h.median()) if len(h) else float("nan")


def avg_lead_time_on_hits(df: pd.DataFrame) -> float:
    """Mean trading days from flag to the first -5% crossing, over hits."""
    lt = df.loc[(df["flag"] == 1) & (df["is_drawdown_day"] == 1), "lead_time"]
    return float(lt.mean()) if len(lt) else float("nan")


def summary(df: pd.DataFrame) -> dict:
    """Bundle every SPEC.md metric into one dict for display / serialization."""
    p, lo, hi = precision(df)
    return {
        "total_flags": total_flags(df),
        "hit_count": hit_count(df),
        "false_alarm_count": false_alarm_count(df),
        "n_days": len(df),
        "base_rate": base_rate(df),
        "precision": p,
        "precision_ci_low": lo,
        "precision_ci_high": hi,
        "hit_rate_tpr": hit_rate_tpr(df),
        "false_alarm_rate_fpr": false_alarm_rate_fpr(df),
        "lift": lift(df),
        "avg_drawdown_on_hits": avg_drawdown_on_hits(df),
        "median_drawdown_on_hits": median_drawdown_on_hits(df),
        "avg_lead_time_on_hits": avg_lead_time_on_hits(df),
    }


def format_headline(s: dict) -> str:
    """Human-readable dashboard string + full SPEC metric block."""
    head = (
        f"This signal flagged elevated risk {s['total_flags']} times. "
        f"{s['hit_count']} were followed by >5% drawdowns within 30 days "
        f"(hit rate: {s['precision']:.1%} "
        f"[95% CI: {s['precision_ci_low']:.1%}-{s['precision_ci_high']:.1%}]). "
        f"{s['false_alarm_count']} were false alarms."
    )
    detail = (
        f"\n  base rate     : {s['base_rate']:.1%}  (any-day {DRAWDOWN_LABEL})"
        f"\n  precision     : {s['precision']:.1%}  (hits / flags)"
        f"\n  hit rate (TPR): {s['hit_rate_tpr']:.1%}  (flags / drawdown days)"
        f"\n  false alarm   : {s['false_alarm_rate_fpr']:.1%}  (flags / calm days, FPR)"
        f"\n  lift          : {s['lift']:.2f}x (precision / base rate; gate needs >= 1.5)"
        f"\n  avg drawdown  : {s['avg_drawdown_on_hits']:.1%} on hits "
        f"(median {s['median_drawdown_on_hits']:.1%})"
        f"\n  avg lead time : {s['avg_lead_time_on_hits']:.1f} trading days on hits"
    )
    return head + detail


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute SPEC.md track-record metrics.")
    parser.add_argument("--input", default="per_day_results.csv", help="Per-day CSV")
    parser.add_argument("--ticker", default="SPY", help="Ticker (V1 universe = SPY)")
    args = parser.parse_args()

    df = load_per_day(Path(args.input), args.ticker)
    print(f"[{args.ticker}] {len(df)} classified days")
    print(format_headline(summary(df)))


if __name__ == "__main__":
    main()
