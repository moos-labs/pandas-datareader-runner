#!/usr/bin/env python3
"""Fetch time series with pandas-datareader — generic runner script.

Pilot defaults (overridable via CLI args, nothing else is hardcoded):
  - FRED series DGS10 (10-Year Treasury Constant Maturity Rate)
  - Stooq symbol ^SPX (S&P 500 index)
  - Window: last ~1 year (365 days) ending today

Each series is fetched independently: one failing does not kill the other.
Every series is saved as a CSV in the output dir, and a summary.json is
written with, per series: source, rows, first/last dates, first/last
values — or the exact error for that series.

Usage:
  python scripts/fetch.py [--fred-series DGS10] [--stooq-symbol ^SPX]
                          [--days 365] [--output-dir results]
"""
import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone


def _scalar(value):
    """Return a plain float from a pandas scalar, dropping NaNs to None."""
    try:
        import math

        f = float(value)
        return None if math.isnan(f) else f
    except Exception:
        return None


def fetch_one(source, symbol, start, end, output_dir):
    """Fetch one series; return a summary dict (never raises)."""
    entry = {"source": source, "symbol": symbol}
    try:
        import pandas_datareader.data as web

        df = web.DataReader(symbol, source, start, end)
        if df is None or len(df) == 0:
            entry["rows"] = 0
            entry["error"] = "empty result: DataReader returned 0 rows"
            return entry

        # Sanitise the symbol for a filename: ^SPX -> SPX, DGS10 -> DGS10
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in symbol).strip("_")
        filename = f"{source}_{safe}.csv"
        path = os.path.join(output_dir, filename)
        df.to_csv(path)
        entry["file"] = filename
        entry["rows"] = int(len(df))
        entry["columns"] = [str(c) for c in df.columns]

        idx = df.index
        entry["first_date"] = str(idx[0].date()) if hasattr(idx[0], "date") else str(idx[0])
        entry["last_date"] = str(idx[-1].date()) if hasattr(idx[-1], "date") else str(idx[-1])

        # First/last values: for single-column frames use that column;
        # for multi-column frames (e.g. Stooq OHLC) report the Close
        # column when present, otherwise the first column.
        if len(df.columns) == 1:
            col = df.columns[0]
        elif "Close" in df.columns:
            col = "Close"
        else:
            col = df.columns[0]
        entry["value_column"] = str(col)
        series = df[col].dropna()
        if len(series):
            entry["first_value"] = _scalar(series.iloc[0])
            entry["last_value"] = _scalar(series.iloc[-1])
            entry["first_value_date"] = (
                str(series.index[0].date())
                if hasattr(series.index[0], "date")
                else str(series.index[0])
            )
            entry["last_value_date"] = (
                str(series.index[-1].date())
                if hasattr(series.index[-1], "date")
                else str(series.index[-1])
            )
        else:
            entry["first_value"] = None
            entry["last_value"] = None
        return entry
    except Exception as exc:  # one failing series must not kill the other
        entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["traceback"] = traceback.format_exc()
        print(f"ERROR fetching {source}:{symbol}: {entry['error']}", file=sys.stderr)
        return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fred-series", default="DGS10",
                        help="FRED series id (default: DGS10); empty string skips FRED")
    parser.add_argument("--stooq-symbol", default="^SPX",
                        help="Stooq symbol (default: ^SPX); empty string skips Stooq")
    parser.add_argument("--days", type=int, default=365,
                        help="Lookback window in days (default: 365)")
    parser.add_argument("--output-dir", default="results",
                        help="Output directory (default: results)")
    args = parser.parse_args()

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=args.days)
    os.makedirs(args.output_dir, exist_ok=True)

    summary = {
        "tool": "pandas-datareader",
        "window": {"start": str(start), "end": str(end), "days": args.days},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "series": [],
    }

    jobs = []
    if args.fred_series:
        jobs.append(("fred", args.fred_series))
    if args.stooq_symbol:
        jobs.append(("stooq", args.stooq_symbol))

    for source, symbol in jobs:
        print(f"Fetching {source}:{symbol} from {start} to {end} ...")
        entry = fetch_one(source, symbol, start, end, args.output_dir)
        summary["series"].append(entry)
        if "error" in entry:
            print(f"  FAILED: {entry['error']}")
        else:
            print(f"  OK: {entry['rows']} rows, "
                  f"{entry.get('first_date')} -> {entry.get('last_date')}, "
                  f"{entry.get('value_column')} "
                  f"{entry.get('first_value')} -> {entry.get('last_value')}")

    summary_path = os.path.join(args.output_dir, "summary.json")
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Wrote {summary_path}")
    # Exit 0 even if a series failed: the failure is data, recorded in
    # summary.json, and the artifact upload (if: always()) carries it.
    return 0


if __name__ == "__main__":
    sys.exit(main())
