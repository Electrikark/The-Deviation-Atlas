# 0004 — Lead time: implementation measures first −5% crossing, SPEC says trough

**Date:** 2026-07-11
**Status:** Documented discrepancy — no code change (owner: "all good")
**Context:** Noticed during Week-8 inspection; SPEC §4 vs backtest.py.

## The discrepancy

- **SPEC §4:** "Avg lead time on hits = trading days from signal to **trough**."
- **Implementation** (`backtest.py::classify_days`): `lead_time` = trading days
  from the flag to the **first day the close is ≤ −5%** vs the flag close —
  i.e. time until the drawdown event *qualifies*, not time to its deepest point.

First-crossing is always ≤ time-to-trough, so the dashboard's "avg lead time
12.0d" is an **earlier-bound** answer to "how much warning did the signal give
before the event materialized?" — arguably the more decision-relevant number,
but not what SPEC literally says.

## Decision

Keep the implementation as-is and document it here. The dashboard label reads
"flag to −5% crossing" (accurate). Changing the metric now — after results have
been seen — would be post-hoc adjustment of a locked metric definition, which
the project forbids. V2 may add `lead_time_to_trough` alongside (not replacing)
the current field, with a SPEC amendment.

## Consequences

- No code change. Dashboard/JSON labels stay explicit about "first crossing".
- V2 backlog item: compute both, amend SPEC §4 wording.
