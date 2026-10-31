#!/usr/bin/env python3
"""Build data/universe/sp500.csv (symbol,sector). Run on the operator's Mac."""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "main/data/constituents.csv"
)


def fetch_csv(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "paper-trader-refresh_sp500/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def parse_constituents(text: str) -> list[tuple[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[str, str]] = []
    for row in reader:
        symbol = (row.get("Symbol") or row.get("symbol") or "").strip().upper()
        sector = (
            row.get("GICS Sector") or row.get("Sector") or row.get("sector") or "Unknown"
        ).strip()
        if symbol:
            rows.append((symbol, sector or "Unknown"))
    rows.sort(key=lambda x: x[0])
    return rows


def write_sp500(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "sector"])
        w.writerows(rows)
    tmp.replace(path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--out", default="data/universe/sp500.csv")
    p.add_argument("--from-file", default="")
    p.add_argument("--min-rows", type=int, default=480)
    args = p.parse_args(argv)

    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8")
        source = args.from_file
    else:
        try:
            text = fetch_csv(args.url)
            source = args.url
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
            return 1

    rows = parse_constituents(text)
    if len(rows) < args.min_rows:
        print(json.dumps({"ok": False, "error": f"only {len(rows)} rows"}), file=sys.stderr)
        return 1

    out = Path(args.out)
    write_sp500(out, rows)
    print(json.dumps({"ok": True, "path": str(out), "rows": len(rows), "source": source}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
