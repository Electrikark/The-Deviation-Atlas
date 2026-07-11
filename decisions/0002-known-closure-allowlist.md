# 0002 — Known-closure allowlist in the gap validator

**Date:** 2026-05-31
**Status:** Accepted
**Context:** CLAUDE.md gotcha #4; required to load full SPY 2000-today history.

## Problem

`data_loader.validate` fails loudly on any calendar gap > 5 days. Pulling SPY
back to 2000 trips it on the **9/11 closure**: the NYSE was shut Sep 11-14,
2001 and reopened Sep 17 — a 7-day gap (last trade Sep 10 -> Sep 17). This is a
real historical fact, not a data error, but the loader cannot ingest the full
history while it raises on it.

## Decision

Add `KNOWN_CLOSURES`, an explicit allowlist keyed by reopening date, each entry
a documented closure. `validate` consults it: a >5-day gap landing on a listed
date is allowed (and printed as a note); **every unlisted >5-day gap still
fails loudly.**

## Why this and not the alternatives

- **Do NOT relax the threshold** (gotcha #4 forbids it). Bumping >5 to >7 or
  adding a blanket `--allow-gaps` flag would silently swallow genuine missing
  data — the exact failure the validator exists to catch.
- An allowlist is a *conscious, auditable, per-closure* override: it lives in
  version control, carries a citation, and reviewers see exactly which gaps are
  sanctioned. Adding a new closure is a deliberate, reviewed edit.

## Entries

| Reopening date | Gap | Reason |
|---|---|---|
| 2001-09-17 | 7d | NYSE closed Sep 11-14, 2001 (9/11 attacks) |

Hurricane Sandy (Oct 29-30, 2012) was a 2-day closure -> 5-day gap, under the
threshold; it never trips the validator and needs no entry.

## Consequences

- The validator's guarantee is unchanged for unknown gaps (still fails loudly).
- Re-run to refresh: `python data_loader.py --tickers SPY --years 26`.
