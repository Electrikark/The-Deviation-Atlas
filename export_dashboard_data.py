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

import numpy as np
import pandas as pd

import backtest   # compute_signal only — reused, never reimplemented (decision 0001)
import metrics
import null_gate
import uncertainty

N_NEIGHBORS = 5   # comparable-cases panel size (Week 8, approved)

# Week 9 user study: the FIXED signal instance shown in both views (?study=1).
# Pinned by flag date so data refreshes cannot move it. Selection criteria
# (pre-stated, neutral): signal 1.05-1.35x threshold, comparable cases split
# 2-3 hits of 5 (ambiguous), not a famous crisis date. Realized outcome: hit,
# -6.5% — revealed only in the post-test debrief, masked in study mode.
STUDY_EVENT_DATE = "2018-02-02"


def latest_state(data_csv: Path) -> dict:
    """
    Current signal state for the most recent trading day in the raw data.

    Runs backtest.compute_signal (the locked formula, same function the
    backtest uses — no second implementation) over the full price series and
    reads the LAST row. Unlike per_day_results.csv this needs no forward
    window: flag state on day t uses only data through t. `ratio` is
    precomputed here so the frontend displays it without doing math.
    """
    df = pd.read_csv(data_csv, parse_dates=["date"])
    sig = backtest.compute_signal(df)
    last = sig.iloc[-1]
    vol, thr = float(last["vol_20"]), float(last["threshold"])
    if math.isnan(vol) or math.isnan(thr):
        raise ValueError(f"{data_csv}: signal not warmed up on latest row")
    return {
        "date": str(last["date"].date()),
        "flag": int(last["flag"]),
        "signal_value": round(vol, 4),
        "threshold": round(thr, 4),
        "ratio": round(vol / thr, 4),
    }


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

    # Clustering-aware 95% CIs (decision 0003). Wilson fields in `s` are kept
    # as the labeled independence-assuming comparison; these are the honest ones.
    bb = uncertainty.paired_block_bootstrap_cis(
        df["flag"].to_numpy(), df["is_drawdown_day"].to_numpy()
    )
    s["precision_ci_bb_low"], s["precision_ci_bb_high"] = map(clean, bb["precision"])
    s["tpr_ci_bb_low"], s["tpr_ci_bb_high"] = map(clean, bb["tpr"])
    s["fpr_ci_bb_low"], s["fpr_ci_bb_high"] = map(clean, bb["fpr"])

    # Gate fragility is computed HERE, not in JS: a PASS whose clustering-aware
    # CI lower bound falls at/below the null 95th pct is flagged, not hidden.
    g["fragile"] = bool(
        g["v1_pass"]
        and s["precision_ci_bb_low"] is not None
        and g["null_p95"] is not None
        and s["precision_ci_bb_low"] <= g["null_p95"]
    )

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

    # Newest-first: the table leads with the most recent flag. Done HERE (order
    # is data, owned by Python) and BEFORE neighbor computation so the baked
    # indices reference the shipped order.
    events.reverse()

    # Comparable cases (Week 8, approved): N nearest past events by
    # |signal_value| distance, precomputed so the frontend does no distance
    # math or sorting. Indices reference this same `events` array.
    sv = np.array([e["signal_value"] for e in events], dtype=float)
    dist = np.abs(sv[:, None] - sv[None, :])
    np.fill_diagonal(dist, np.inf)
    order = np.argsort(dist, axis=1, kind="stable")[:, :N_NEIGHBORS]
    for i, e in enumerate(events):
        e["neighbors"] = [int(j) for j in order[i]]

    # Study event: located by date (refresh-proof), index + ratio precomputed
    # here so neither frontend searches or does math. Fails loudly if missing.
    study_idx = next((i for i, e in enumerate(events)
                      if e["flag_date"] == STUDY_EVENT_DATE), None)
    if study_idx is None:
        raise ValueError(f"study event {STUDY_EVENT_DATE} not found in events")
    se = events[study_idx]
    study_event = {
        **se,
        "index": study_idx,
        "ratio": round(se["signal_value"] / se["threshold"], 4),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ticker": ticker,
        "latest": latest_state(Path("data") / f"{ticker}.csv"),
        "study_event": study_event,
        "headline": s,
        "null_gate": g,
        "ci_method": {
            "name": "paired circular block bootstrap (Politis & Romano 1994)",
            "block": bb["block"],
            "runs": bb["n_runs"],
            "seed": bb["seed"],
            "assumption": (
                "Resamples 30-trading-day blocks, so consecutive flag-days from "
                "one volatility regime stay together — does NOT assume "
                "independent flags. The narrower Wilson interval (which does) "
                "is shown for comparison on precision."
            ),
        },
        "n_neighbors": N_NEIGHBORS,
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
