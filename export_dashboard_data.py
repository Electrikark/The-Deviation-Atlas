#!/usr/bin/env python3
"""
export_dashboard_data.py — Export ONE static JSON for the track-record dashboard.

Pure CONSUMER of existing logic (decision 0001): imports metrics + null_gate,
reads per_day_results.csv, computes nothing new. The frontend (dashboard/) only
displays these pre-computed values; no metric math happens in JavaScript.

Events come from the per-day file's flag rows — the same single source of truth
as backtest_results.csv, plus lead_time. False alarms are NEVER filtered.

USAGE: python export_dashboard_data.py [--input per_day_results.csv]
       [--ticker SPY] [--output dashboard/dashboard_data.json]
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import metrics
import null_gate


def clean(x):
    """NaN/numpy -> JSON-safe (None / native python)."""
    if isinstance(x, float) and math.isnan(x):
        return None
    if hasattr(x, "item"):          # numpy scalar
        return clean(x.item())
    return x


def build_payload(df, ticker: str) -> dict:
    s = {k: clean(v) for k, v in metrics.summary(df).items()}
    g = {k: clean(v) for k, v in null_gate.run_gate(df).items()}

    flags = df[df["flag"] == 1]
    events = [
        {
            "flag_date": r["date"],
            "signal_value": clean(round(r["vol_20"], 4)),
            "threshold": clean(round(r["threshold"], 4)),
            "max_drawdown_30d": clean(round(r["max_drawdown_30d"], 4)),
            "outcome": "hit" if r["is_drawdown_day"] == 1 else "false_alarm",
            "lead_time": clean(r["lead_time"]),
        }
        for r in flags.to_dict("records")
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ticker": ticker,
        "headline": s,
        "null_gate": g,
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export dashboard JSON.")
    parser.add_argument("--input", default="per_day_results.csv", help="Per-day CSV")
    parser.add_argument("--ticker", default="SPY", help="Ticker (V1 universe = SPY)")
    parser.add_argument("--output", default="dashboard/dashboard_data.json")
    args = parser.parse_args()

    df = metrics.load_per_day(Path(args.input), args.ticker)
    payload = build_payload(df, args.ticker.upper())

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, allow_nan=False), encoding="utf-8")

    n_fa = sum(1 for e in payload["events"] if e["outcome"] == "false_alarm")
    print(f"[ok] {out}: {len(payload['events'])} events "
          f"({n_fa} false alarms included), "
          f"v1_pass={payload['null_gate']['v1_pass']}, "
          f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
