# 0003 — Clustering-aware CIs via paired circular block bootstrap

**Date:** 2026-07-11
**Status:** Accepted (owner approved option (a), Week 8)
**Context:** Week-8 inspection 1; backtest.py caveat #2 (flags are not independent).

## Problem

`metrics.py` computed a Wilson score CI for precision only, treating each of
the 1,089 flag-days as an independent Bernoulli trial. Flags cluster — one
volatility regime produces many consecutive flag-days that resolve on the same
outcome (e.g. 2002-07-10…16). The effective sample size is far below the
nominal N, so the Wilson interval understates true uncertainty and is
methodologically inconsistent with the project's own documented caveat.
TPR and FPR had no CI at all.

## Decision

Add `uncertainty.py`: a **paired circular block bootstrap** (Politis & Romano
1994, block = 30 trading days, 1,000 resamples, fixed seed) producing 95%
percentile CIs for precision, TPR, and FPR. "Paired" means each block carries
its (flag, is_drawdown_day) days together, preserving flag↔outcome alignment —
unlike `null_gate.py`'s bootstrap, which deliberately breaks that alignment to
build the null. Same resampling scheme, two distinct purposes.

The Wilson CI is **retained** in the export, explicitly labeled as the
independence-assuming comparison — deleting it would hide how much the naive
method flatters the result, which is exactly the kind of information this
project exists to surface.

## Gate fragility

The export computes `null_gate.fragile = v1_pass AND (precision bb-CI lower
bound <= null 95th percentile)`. A fragile pass renders as "⚠ PASS (fragile)"
in the dashboard — visible, not smoothed over. Computed in Python; the
frontend only displays it.

## Consequences

- `dashboard_data.json` gains `precision/tpr/fpr_ci_bb_low/high`, a
  `ci_method` disclosure block, and `null_gate.fragile`.
- Dashboard shows ranges beside precision, TPR, FPR, with method + assumption
  on hover and in a permanent footnote.
- No SPEC-locked parameter or signal logic touched.
