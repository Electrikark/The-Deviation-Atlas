# The Deviation Atlas

Pipeline: `data_loader.py` → `backtest.py` → `metrics.py` / `null_gate.py` → dashboard.

## Dashboard (track-record view)

Static frontend in `dashboard/` — plain HTML/CSS/JS, no build step, no backend.
It only *displays* values pre-computed in Python; no metric math runs in JS.

```bash
# 1. Regenerate the data file (runs metrics.py + null_gate.py, writes ONE JSON)
python export_dashboard_data.py            # -> dashboard/dashboard_data.json

# 2. View locally (fetch() needs http://, not file://)
python -m http.server 8123                 # then open http://localhost:8123/dashboard/
```

**GitHub Pages:** works unchanged — the page fetches `dashboard_data.json` by
relative path. Enable Pages on the repo (serve from root or `/dashboard`) and
commit `dashboard/index.html` + `dashboard/dashboard_data.json`. Re-run the
export and re-commit the JSON to refresh the numbers.

---

# data_loader.py

Pulls daily price data from Yahoo Finance, validates it, and writes one CSV per ticker.

## Install

```bash
pip install yfinance pandas
```

## Run

```bash
python data_loader.py --tickers SPY,AAPL,MSFT --years 2
```

| Flag | Required | Default | Notes |
|---|---|---|---|
| `--tickers` | yes | — | Comma-separated symbols |
| `--years` | no | 2 | Years of history from today |
| `--output-dir` | no | `data` | CSVs written here, one per ticker |

## Output

`<TICKER>.csv` with columns: `date, open, high, low, close, volume`.

**Prices are split- and dividend-adjusted** (yfinance `auto_adjust=True`). This matters for the Deviation Atlas: raw close prices have phantom ~0.5% drops on dividend ex-dates that would generate spurious volatility-spike signals. The locked spec's "close" should be read as adjusted close.

## Validation

The script fails loudly (non-zero exit, error to stderr) if any ticker has:
- Nulls in any required column
- Non-monotonic dates
- A gap > 5 calendar days between consecutive rows (long weekends ≤ 4 days are fine)

Known legitimate closures (9/11/2001 → 9/17/2001; Sandy Oct 29–30, 2012) will trip the gap check on purpose. Document and override deliberately rather than relaxing the validator.

Failed tickers don't block successful ones — partial output is written, but exit code is 1 if anything failed.

## What this doesn't do

- No retries / backoff on transient network failures (add for production).
- No caching — every run hits Yahoo. Fine at this scale; revisit if you start iterating fast.
- No cross-check against a second source (FRED `SP500` for SPY). Worth doing once a quarter; not automated here.
