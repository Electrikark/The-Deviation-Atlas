# Week 9 User Test — Score-Only vs. Wrongness-First Presentation

**Research question:** Does showing uncertainty and failure history (the
"wrongness-first" track-record view) change how much confidence people place
in the same risk signal, compared with a conventional score-only view?

**Design:** Within-subjects, two conditions, counterbalanced order. Every
participant sees the SAME fixed signal instance in both views and answers the
SAME three questions after each view.

---

## The fixed signal instance

Both views are pinned to the flag of **2018-02-02** (SPY, 20-day realized vol
0.1210 vs threshold 0.1010 — 120% of alert level). Pinned by date in the
export, so data refreshes cannot change what participants see.

| Condition | URL (append to the deployed site root) |
|---|---|
| A — Score-only | `dashboard/score_only.html?study=1` |
| B — Wrongness-first | `dashboard/track-record.html?study=1` |

In condition B the instance's own realized outcome displays as "◌ pending" —
participants must not learn what actually happened until the debrief.

**Facilitator note — do not reveal:** the flag was a hit (−6.47% within 30
trading days; −5% crossed in 4). Disclose only in the debrief.

---

## Pre-test framing script (read aloud, verbatim, before EITHER view)

> "You'll see two versions of a tool that monitors risk in a stock-market
> fund. Imagine you have savings invested in this fund. The tool has just
> raised an alert today. I'll show you one version at a time and ask the same
> few questions after each. There are no right or wrong answers — I'm testing
> the tool's presentation, not you."

Do NOT say: which view is "ours," which is newer, that one shows "more
information," or anything implying a preferred answer. Answer clarifying
questions about *mechanics* ("what does this number mean?") by reading the
on-screen text only.

## Counterbalancing

Alternate order by participant number:

- **Odd participants (P1, P3, P5, …):** score-only first, then wrongness-first.
- **Even participants (P2, P4, P6, …):** wrongness-first first, then score-only.

Record the order in TEST_RESULTS.md. Do not deviate — order effects are the
main confound this controls.

## Procedure (per participant)

1. Read the framing script.
2. Open the first view (per counterbalancing). Let the participant look and
   scroll freely. No time limit; typical 1–3 minutes. In condition B they may
   click history rows — allow it.
3. Ask the three post-view questions (below). Record answers verbatim.
4. Open the second view. Repeat step 3, identical wording.
5. Debrief (below).

## Post-view questions (identical after EACH view — ask in this order)

1. "On a scale of 1–10, how confident are you that this alert predicts a
   real drawdown — that the fund will actually drop by 5% or more in the
   next month or so?"
2. "Would you act on this signal — for example, move some of your savings
   out of the fund? Why or why not?"
3. "How would you describe this tool's reliability in one sentence?"

## Debrief (read after both views are done)

> "Both screens showed the same underlying alert, from the same model, using
> the same data — they differ only in how much of the model's track record
> they show. The alert you saw was a real historical one from February 2018;
> the fund did fall about 6.5% within the following month, so that alert was
> a 'hit.' Historically, alerts from this model are followed by such a drop
> roughly 4 times in 10. Nothing in this test was financial advice, and the
> tool is a research prototype. Do you have any questions?"

## Known limitations (log with results; do not mention during the test)

- The track-record view's aggregate statistics (precision, CIs, null gate)
  are computed over the FULL 2000–2026 history, including data after
  2018-02-02. A true as-of-2018 replay would need a separate pipeline —
  out of scope for Week 9. The framing avoids dating the track record.
- Within-subjects design: the second view is always seen with knowledge of
  the first. Counterbalancing controls for this on average but n must be
  even, and per-order deltas should be reported, not just the pooled delta.
- Participants are a convenience sample; treat findings as directional, not
  significant.
