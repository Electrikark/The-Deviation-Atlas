#!/usr/bin/env python3
"""
uncertainty.py — Clustering-aware CIs via paired circular block bootstrap.

Decision 0003. The Wilson CI in metrics.py treats each flag-day as an
independent Bernoulli trial; backtest.py caveat #2 says flags cluster (one vol
regime -> many consecutive flag-days), so Wilson understates uncertainty.

Here we resample PAIRED (flag, is_drawdown_day) days in contiguous circular
blocks (Politis & Romano 1994 — the same scheme null_gate.py uses, block=30).
Unlike the null model, the flag<->outcome alignment is kept intact inside each
block; only the sampling of which regimes enter each pseudo-history varies.
Percentile CIs from the resampled metric distributions widen honestly with the
clustering. Fixed seed -> reproducible exports.
"""
import numpy as np

BLOCK_DEFAULT = 30
N_RUNS_DEFAULT = 1000


def paired_block_bootstrap_cis(flag, ddday, block=BLOCK_DEFAULT,
                               n_runs=N_RUNS_DEFAULT, seed=0, alpha=0.05):
    """
    95% percentile CIs for precision, TPR, and FPR under paired block resampling.

    flag, ddday: 0/1 day-aligned arrays. Returns
      {"precision": (lo, hi), "tpr": (lo, hi), "fpr": (lo, hi),
       "valid_runs": {...}, "block": int, "n_runs": int, "seed": int}
    Resamples with an empty denominator are dropped for that metric only
    ((None, None) if nothing survives).
    """
    rng = np.random.default_rng(seed)
    flag = np.asarray(flag, dtype=bool)
    ddday = np.asarray(ddday, dtype=bool)
    n = len(flag)
    n_blocks = int(np.ceil(n / block))
    offsets = np.arange(block)
    prec, tpr, fpr = [], [], []
    for _ in range(n_runs):
        starts = rng.integers(0, n, size=n_blocks)
        idx = ((starts[:, None] + offsets[None, :]) % n).ravel()[:n]
        f, d = flag[idx], ddday[idx]
        n_flags, n_dd = int(f.sum()), int(d.sum())
        tp = int((f & d).sum())
        if n_flags:
            prec.append(tp / n_flags)
        if n_dd:
            tpr.append(tp / n_dd)
        if n_dd < n:
            fpr.append(int((f & ~d).sum()) / (n - n_dd))
    lo_p, hi_p = 100 * alpha / 2, 100 * (1 - alpha / 2)

    def ci(vals):
        if not vals:
            return (None, None)
        return (float(np.percentile(vals, lo_p)), float(np.percentile(vals, hi_p)))

    return {
        "precision": ci(prec),
        "tpr": ci(tpr),
        "fpr": ci(fpr),
        "valid_runs": {"precision": len(prec), "tpr": len(tpr), "fpr": len(fpr)},
        "block": block,
        "n_runs": n_runs,
        "seed": seed,
    }
