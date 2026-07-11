# 0001 — Per-day classification: single source of truth in backtest.py

**Date:** 2026-05-31
**Status:** Accepted
**Context:** CLAUDE.md gotcha #1 / open Week-6 decision.

## Problem

`backtest_results.csv` contains flag-day events only (TP + FP). The SPEC.md
metrics base rate, true hit rate (TPR), false alarm rate (FPR), and lift all
require per-day classification: for *every* trading day (flagged or not),
(a) did the signal flag it, and (b) was it followed by a >=5% drawdown within
30 trading days. Two options were open:

1. `backtest.py` emits a second per-day output CSV.
2. `metrics.py` re-derives per-day classification from the raw ticker CSVs.

## Decision

**Option 1.** `backtest.py` owns ALL signal and outcome computation and emits
both a per-flag CSV (unchanged format) and a per-day CSV. `metrics.py` and
`null_gate.py` are pure consumers — they never recompute the signal.

## Why

- **Single source of truth.** This is a wrongness-first project. Option 2
  duplicates the look-ahead-sensitive logic (`compute_signal`, the forward
  drawdown window) in a second file. A leak could exist in one and not the
  other, and the two outputs could disagree without anyone noticing — the
  exact silent-drift failure mode the project rejects on principle.
- **Both outputs now derive from one function** (`classify_days`), so per-flag
  and per-day numbers are guaranteed consistent by construction.
- Methodology is unchanged: all spec-locked parameters (20d vol window, 252d
  median, 1.5x mult, 30d horizon, -5% threshold) are untouched. This change
  ADDS an output; it does not alter the signal.

## Consequences

- `backtest.py` gains a `--per-day-output` (default `per_day_results.csv`) with
  columns: ticker, date, close, vol_20, threshold, flag, max_drawdown_30d,
  is_drawdown_day, lead_time.
- `evaluate_flag` is folded into `classify_days` to avoid a parallel code path.
- The per-flag CSV format (`backtest_results.csv`) is byte-for-byte unchanged.
