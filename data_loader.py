#!/usr/bin/env python3
"""data_loader.py — Pull, validate, and save daily price data via yfinance."""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def fetch(ticker: str, years: int) -> pd.DataFrame:
    """Download `years` of daily data for `ticker`, return clean DataFrame."""
    start = pd.Timestamp.today() - pd.DateOffset(years=years)
    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"{ticker}: no data returned")
    # yfinance sometimes returns a MultiIndex even for single tickers — flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    return df[COLUMNS]


def validate(df: pd.DataFrame, ticker: str) -> None:
    """Fail loudly on nulls, unsorted dates, or suspicious calendar gaps."""
    if df.isnull().any().any():
        bad = df.columns[df.isnull().any()].tolist()
        raise ValueError(f"{ticker}: nulls in columns {bad}")
    if not df["date"].is_monotonic_increasing:
        raise ValueError(f"{ticker}: dates not sorted")
    gaps = df["date"].diff().dt.days
    # >5 days catches missing data; long weekends (≤4d) are allowed.
    # Known closures (9/11, Sandy 2012) will trigger this deliberately.
    if gaps.max() > 5:
        loc = gaps.idxmax()
        raise ValueError(
            f"{ticker}: {int(gaps.max())}-day gap at {df.loc[loc, 'date'].date()}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull daily price data to CSV.")
    parser.add_argument("--tickers", required=True, help="Comma-separated, e.g. SPY,AAPL")
    parser.add_argument("--years", type=int, default=2, help="Years of history (default 2)")
    parser.add_argument("--output-dir", default="data", help="Output dir (default ./data)")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    failed = []
    for ticker in tickers:
        try:
            df = fetch(ticker, args.years)
            validate(df, ticker)
            path = out / f"{ticker}.csv"
            df.to_csv(path, index=False, date_format="%Y-%m-%d")
            print(f"✓ {ticker}: {len(df)} rows -> {path}")
        except Exception as e:
            print(f"✗ {ticker}: {e}", file=sys.stderr)
            failed.append(ticker)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
