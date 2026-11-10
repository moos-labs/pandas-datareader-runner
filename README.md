# pandas-datareader-runner

Runs [pandas-datareader](https://pandas-datareader.readthedocs.io/) data
fetches on GitHub Actions — part of a one-public-repo-per-tool pattern:
each tool gets its own repo, the commands to execute live in a repository
**Actions variable** (not in code), runs are triggered manually, and
outputs are collected as artifacts.

pandas-datareader provides a uniform `DataReader` interface to many
remote data sources — FRED (Federal Reserve Economic Data), Stooq,
World Bank, OECD, and more — returning pandas DataFrames.

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

## Pilot

Defaults fetch, for the last ~1 year:

- **FRED `DGS10`** — 10-Year Treasury Constant Maturity Rate (daily, %)
- **Stooq `^SPX`** — S&P 500 index (daily OHLCV; summary values use Close)

See the `results` artifact of the first dispatched run for the verified
pilot figures.
