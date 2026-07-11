#!/usr/bin/env python3
"""
null_gate.py — V1 ship gate: beat a random-firing Monte Carlo baseline.

SPEC.md V1 ship gate (BOTH must pass):
  1. lift >= 1.5
  2. precision exceeds the 95th percentile of N=1,000 random-firing runs.

The null model preserves auto-correlation (CLAUDE.md gotcha #2). Volatility
clusters, so flags arrive in runs; a naive i.i.d. random-firing null has far too
little variance and would declare almost anything significant. We instead use a
CIRCULAR BLOCK BOOTSTRAP (Politis & Romano, 1994) with ~30-day blocks: resample
contiguous 30-day blocks of the real flag indicator to build a synthetic flag
series with the SAME clustering structure, then measure its precision against the
real (fixed) drawdown-day outcomes. This breaks the flag<->outcome alignment
while keeping each series' own dependence intact — the honest, harder-to-pass null.

V1 universe is SPY only (--ticker defaults to SPY).
"""
import argparse
from pathlib import Path

import numpy as np

import metrics

BLOCK_DEFAULT = 30      # ~30 trading days, matches the forward horizon / vol clustering
N_RUNS_DEFAULT = 1000
LIFT_GATE = 1.5
PERCENTILE_GATE = 95


def circular_block_bootstrap_precision(flag, ddday, block, n_runs, seed):
    """
    Null distribution of precision under circular block bootstrap of the flags.

    flag, ddday: 0/1 arrays aligned by day. Returns an array of n_runs precisions.
    Synthetic flag count varies run-to-run (correct: it captures that sampling
    variability). Runs that draw zero flags yield NaN and are dropped downstream.
    """
    rng = np.random.default_rng(seed)
    flag = np.asarray(flag, dtype=int)
    ddday = np.asarray(ddday, dtype=bool)
    n = len(flag)
    if flag.sum() == 0 or n == 0:
        return np.array([])
    ext = np.concatenate([flag, flag])            # circular wrap
    n_blocks = int(np.ceil(n / block))
    out = np.full(n_runs, np.nan)
    for i in range(n_runs):
        starts = rng.integers(0, n, size=n_blocks)
        synth = np.concatenate([ext[s:s + block] for s in starts])[:n].astype(bool)
        sf = synth.sum()
        if sf:
            out[i] = (synth & ddday).sum() / sf
    return out[~np.isnan(out)]


def run_gate(df, block=BLOCK_DEFAULT, n_runs=N_RUNS_DEFAULT, seed=0) -> dict:
    """Run both gates on a per-day DataFrame (already ticker-filtered)."""
    real_precision = metrics.precision(df)[0]
    real_lift = metrics.lift(df)
    null = circular_block_bootstrap_precision(
        df["flag"].to_numpy(), df["is_drawdown_day"].to_numpy(), block, n_runs, seed
    )

    if null.size:
        p95 = float(np.percentile(null, PERCENTILE_GATE))
        # empirical p-value: P(null precision >= real precision)
        p_value = float((null >= real_precision).mean())
    else:
        p95, p_value = float("nan"), float("nan")

    precision_pass = bool(np.isfinite(real_precision) and real_precision > p95)
    lift_pass = bool(np.isfinite(real_lift) and real_lift >= LIFT_GATE)
    return {
        "real_precision": real_precision,
        "real_lift": real_lift,
        "null_runs": int(null.size),
        "null_p95": p95,
        "null_mean": float(null.mean()) if null.size else float("nan"),
        "p_value": p_value,
        "lift_gate_pass": lift_pass,
        "precision_gate_pass": precision_pass,
        "v1_pass": lift_pass and precision_pass,
    }


def format_verdict(g: dict, block: int) -> str:
    yn = lambda b: "PASS" if b else "FAIL"
    return (
        f"V1 SHIP GATE (circular block bootstrap, block={block}, "
        f"{g['null_runs']} valid runs)\n"
        f"  real precision : {g['real_precision']:.1%}\n"
        f"  null precision : mean {g['null_mean']:.1%}, "
        f"95th pct {g['null_p95']:.1%}\n"
        f"  empirical p    : {g['p_value']:.3f}\n"
        f"  real lift      : {g['real_lift']:.2f}x (need >= {LIFT_GATE})\n"
        f"  --------------------------------------------------\n"
        f"  lift gate      : {yn(g['lift_gate_pass'])}\n"
        f"  precision gate : {yn(g['precision_gate_pass'])} "
        f"(real precision > null 95th pct)\n"
        f"  V1 VERDICT     : {yn(g['v1_pass'])}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the V1 Monte Carlo null gate.")
    parser.add_argument("--input", default="per_day_results.csv", help="Per-day CSV")
    parser.add_argument("--ticker", default="SPY", help="Ticker (V1 universe = SPY)")
    parser.add_argument("--block", type=int, default=BLOCK_DEFAULT, help="Block length")
    parser.add_argument("--runs", type=int, default=N_RUNS_DEFAULT, help="MC runs")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed (reproducible)")
    args = parser.parse_args()

    df = metrics.load_per_day(Path(args.input), args.ticker)
    print(f"[{args.ticker}] {len(df)} classified days, "
          f"{metrics.total_flags(df)} flags, base rate {metrics.base_rate(df):.1%}")
    print(format_verdict(run_gate(df, args.block, args.runs, args.seed), args.block))


if __name__ == "__main__":
    main()
