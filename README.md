# pandas-datareader-runner

Runs [pandas-datareader](https://pandas-datareader.readthedocs.io/) data
fetches on GitHub Actions — part of a one-public-repo-per-tool pattern:
each tool gets its own repo, the commands to execute live in a repository
**Actions variable** (not in code), runs are triggered manually, and
outputs are collected as artifacts.

pandas-datareader provides a uniform `DataReader` interface to remote
data sources — FRED (Federal Reserve Economic Data), World Bank, OECD,
Fama/French, and more — returning pandas DataFrames.

## The pattern (one repo per tool)

1. **Edit the commands**: repo *Settings → Secrets and variables → Actions →
   Variables* → set the `COMMANDS` variable to whatever shell commands this
   run should execute (multi-line works). The same can be done through the
   GitHub API (`PUT /repos/{owner}/{repo}/actions/variables/COMMANDS`).
   Current value:
   ```
   mkdir -p results
   python scripts/fetch.py 2>&1 | tee results/run.log
   ```
2. **Trigger manually**: *Actions* tab → "Run analysis" → *Run workflow*
   (or `POST /repos/{owner}/{repo}/actions/workflows/run.yml/dispatches`).
   The workflow has **no other triggers** — it runs only when dispatched.
3. **Collect results**: the workflow uploads everything under `results/` as
   the `results` build artifact (`if: always()`, so partial results survive
   a failing step). Download it from the run page or via the API.

The workflow itself is generic: checkout → Python 3.11 →
`pip install -r requirements.txt` → run `${{ vars.COMMANDS }}` → upload
`results/`. To run a different fetch, change the variable (and/or the
script's CLI args in it) — not the workflow.

## The tool

`scripts/fetch.py` is generic: series and parameters are CLI args, nothing
is hardcoded beyond the pilot defaults.

```
python scripts/fetch.py [--fred-series DGS10] [--stooq-symbol ^SPX]
                        [--days 365] [--output-dir results]
```

- `--fred-series` — any FRED series id (empty string skips FRED)
- `--stooq-symbol` — any Stooq symbol (empty string skips Stooq)
- `--days` — lookback window in days (default 365)
- `--output-dir` — where CSVs + `summary.json` go (default `results`)

Each series is fetched independently — one failing does not kill the
other. Outputs per run, in `results/`:

- `fred_<SERIES>.csv` / `stooq_<SYMBOL>.csv` — the raw series as returned
- `summary.json` — per series: `source`, `symbol`, `rows`, `first_date`,
  `last_date`, `value_column`, `first_value`, `last_value` — or the exact
  `error` for that series
- `run.log` — the console log (via `tee` in `COMMANDS`)

## Pilot — verified results (10 Nov 2026)

Pilot defaults fetch, for the last ~1 year:

- **FRED `DGS10`** — 10-Year Treasury Constant Maturity Rate (daily, %)
- **Stooq `^SPX`** — S&P 500 index (daily OHLCV; summary values use Close)

**FRED `DGS10` — works.** Verified identical in run 1 (current
pandas-datareader) and run 3 (pinned legacy stack); the two
`fred_DGS10.csv` files are byte-identical:

- 260 rows, 2025-11-10 → 2026-11-06
- First value 4.13 (2025-11-10), last value 4.86 (2026-11-06)

**Stooq `^SPX` — data source genuinely broken in 2026**, in both library
generations:

- Current pandas-datareader (0.11.x): the Stooq reader was **removed** in
  v0.11.0 (June 2026), which narrowed the package to macro/factor sources
  (FRED, Fama/French, World Bank, OECD, …). Exact error from run 1:
  `NotImplementedError: data_source='stooq' is not implemented`
- Pinned legacy stack (`pandas-datareader==0.10.0`, the last release with
  a Stooq reader — see `requirements.txt`): the reader runs, but Stooq's
  CSV endpoint itself no longer serves the file. Exact error from run 3:
  `RemoteDataError: Unable to read URL: https://stooq.com/q/d/l/?s=%5ESPX&i=d&d1=20251110&d2=20261110`
  — stooq.com answers with an HTML page: *"The page you requested does not
  exist or has been moved"* (Stooq moved CSV downloads behind an API key
  in 2026).

That is why `requirements.txt` stays on the pinned legacy stack: it is
the configuration in which the Stooq failure is the genuine upstream
failure (endpoint gone) rather than a library removal, and FRED output is
identical either way. To fetch a different FRED series, pass
`--fred-series <ID>` via the `COMMANDS` variable.
