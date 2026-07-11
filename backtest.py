#!/usr/bin/env python3
"""
backtest.py — Replay the Deviation Atlas volatility-spike signal on historical data.

METHODOLOGY (per SPEC.md v0.1) — no look-ahead by construction:
    log_ret_t  = log(close_t / close_{t-1})
    vol_20_t   = std(log_ret_{t-19..t}) * sqrt(252)        # 20-day realized vol, annualized
    threshold  = 1.5 * median(vol_20_{t-251..t})           # 1.5x trailing 1-year median
    flag_t     = 1 if vol_20_t > threshold else 0

Forward window: 30 TRADING days (rows), [t+1, t+30].
Drawdown: max_drawdown_30d = min(close_{t+1..t+30}) / close_t - 1   (NEGATIVE; -0.07 = 7% drop)
Outcome:  "hit" if max_drawdown_30d <= -0.05 else "false_alarm".

CAVEATS — read before interpreting:
  1. Flags within last 30 rows of data are EXCLUDED (incomplete forward window).
  2. Consecutive flags are NOT independent (vol clustering). Significance must account for this.
  3. No flags fire in the first ~272 trading days (rolling windows warming up).
  4. Output has TP+FP only — no FN/TN. Hit rate / FPR require per-day data (see metrics.py).
  5. Uses adjusted close (data_loader.py auto_adjust=True); raw close would create phantom DDs.

USAGE: python backtest.py --data-dir data --output backtest_results.csv [--tickers SPY,AAPL]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

VOL_WINDOW = 20
MEDIAN_WINDOW = 252
THRESHOLD_MULT = 1.5
FORWARD_DAYS = 30
DRAWDOWN_THRESHOLD = -0.05


def compute_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Add log_ret, vol_20, threshold, flag columns. No look-ahead by construction."""
    df = df.sort_values("date").reset_index(drop=True).copy()
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
    df["vol_20"] = df["log_ret"].rolling(VOL_WINDOW).std() * np.sqrt(252)
    df["threshold"] = df["vol_20"].rolling(MEDIAN_WINDOW).median() * THRESHOLD_MULT
    df["flag"] = (df["vol_20"] > df["threshold"]).astype(int)
    return df


def classify_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    SINGLE SOURCE OF TRUTH for outcomes (decision 0001).

    For every row with a complete 30-row forward window, compute the drawdown
    outcome a flag on that day WOULD have had. Outcome depends only on forward
    prices, so it is defined for every day regardless of whether the signal
    actually flagged — which is exactly what base rate / TPR / FPR / lift need.

    Adds: max_drawdown_30d, has_window, is_drawdown_day, lead_time.
      lead_time = trading days from t to the FIRST day in [t+1, t+30] whose
                  close is <= -5% vs close_t (NaN if the threshold is never hit).
    """
    df = df.copy()
    n = len(df)
    close = df["close"].to_numpy(dtype=float)
    max_dd = np.full(n, np.nan)
    lead = np.full(n, np.nan)
    for t in range(n):
        end = t + FORWARD_DAYS
        if end >= n:
            break  # incomplete forward window — all later rows are too
        ct = close[t]
        window = close[t + 1 : end + 1]          # rows t+1 .. t+30 (30 values)
        rel = window / ct - 1.0
        max_dd[t] = rel.min()
        crossed = np.where(rel <= DRAWDOWN_THRESHOLD)[0]
        if crossed.size:
            lead[t] = int(crossed[0]) + 1        # +1: window starts at t+1
    df["max_drawdown_30d"] = max_dd
    df["has_window"] = ~np.isnan(max_dd)
    df["is_drawdown_day"] = (df["max_drawdown_30d"] <= DRAWDOWN_THRESHOLD).astype(int)
    df.loc[~df["has_window"], "is_drawdown_day"] = pd.NA
    df["lead_time"] = lead
    return df


def backtest_ticker(path: Path):
    """Run backtest on one ticker's CSV; return (per_flag_df, per_day_df)."""
    ticker = path.stem
    df = pd.read_csv(path, parse_dates=["date"])
    df = compute_signal(df)
    df = classify_days(df)

    valid = df[df["has_window"]].copy()          # drop incomplete forward windows
    valid["ticker"] = ticker
    valid["is_drawdown_day"] = valid["is_drawdown_day"].astype(int)

    per_day = valid[[
        "ticker", "date", "close", "vol_20", "threshold", "flag",
        "max_drawdown_30d", "is_drawdown_day", "lead_time",
    ]].copy()

    flags = valid[valid["flag"] == 1]
    per_flag = pd.DataFrame({
        "ticker": ticker,
        "flag_date": flags["date"].dt.date,
        "signal_value": flags["vol_20"].round(4),
        "max_drawdown_30d": flags["max_drawdown_30d"].round(4),
        "outcome": np.where(flags["is_drawdown_day"] == 1, "hit", "false_alarm"),
    }, columns=["ticker", "flag_date", "signal_value", "max_drawdown_30d", "outcome"])
    return per_flag, per_day


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Deviation Atlas backtest.")
    parser.add_argument("--data-dir", default="data", help="Dir of per-ticker CSVs")
    parser.add_argument("--output", default="backtest_results.csv", help="Per-flag CSV path")
    parser.add_argument("--per-day-output", default="per_day_results.csv",
                        help="Per-day classification CSV (decision 0001)")
    parser.add_argument("--tickers", default=None, help="Optional comma-separated filter")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    csvs = sorted(data_dir.glob("*.csv"))
    if args.tickers:
        wanted = {t.strip().upper() for t in args.tickers.split(",")}
        csvs = [p for p in csvs if p.stem.upper() in wanted]
    if not csvs:
        print(f"No CSVs found in {data_dir}", file=sys.stderr)
        sys.exit(1)

    all_flags, all_days = [], []
    for path in csvs:
        per_flag, per_day = backtest_ticker(path)
        n_flags = len(per_flag)
        n_hits = int((per_flag["outcome"] == "hit").sum()) if n_flags else 0
        precision = n_hits / n_flags if n_flags else float("nan")
        print(f"[ok] {path.stem}: {n_flags} flags, {n_hits} hits, "
              f"precision={precision:.2%}, {len(per_day)} classified days")
        all_flags.append(per_flag)
        all_days.append(per_day)

    combined = pd.concat(all_flags, ignore_index=True)
    combined.to_csv(args.output, index=False)
    per_day_all = pd.concat(all_days, ignore_index=True)
    per_day_all.to_csv(args.per_day_output, index=False, date_format="%Y-%m-%d")

    print(f"\nWrote {len(combined)} flag events to {args.output} (TP+FP only)")
    print(f"Wrote {len(per_day_all)} classified days to {args.per_day_output} "
          f"(per-day data for base rate / TPR / FPR / lift -> metrics.py)")


if __name__ == "__main__":
    main()
