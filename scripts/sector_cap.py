#!/usr/bin/env python3
"""Sector counting and max-per-sector checks per master spec Section 7.6."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

BROAD_MARKET_ETFS = frozenset({"SPY", "VOO", "IVV", "VTI", "QQQ", "DIA", "IWM"})


def load_etf_sectors(csv_path: Path | str) -> dict[str, str]:
    path = Path(csv_path)
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip().upper()
            sector = (row.get("sector") or "").strip()
            if sym and sector:
                out[sym] = sector
    return out


def load_sp500_sectors(csv_path: Path | str) -> dict[str, str]:
    path = Path(csv_path)
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip().upper()
            sector = (row.get("sector") or "").strip()
            if sym:
                out[sym] = sector or "Unknown"
    return out


def resolve_sector(
    symbol: str,
    *,
    asset_type: str = "stock",
    mcp_sector: Optional[str] = None,
    sp500_sectors: Optional[Mapping[str, str]] = None,
    etf_sectors: Optional[Mapping[str, str]] = None,
) -> str:
    sym = symbol.strip().upper()
    at = asset_type.lower()
    sp500_sectors = sp500_sectors or {}
    etf_sectors = etf_sectors or {}

    if at == "etf":
        if sym in BROAD_MARKET_ETFS:
            return "Broad Market"
        if sym in etf_sectors:
            return etf_sectors[sym]
        return "Other ETF"

    # Prefer S&P GICS sector names; Robinhood fundamentals use a different taxonomy
    # (e.g. AAPL = "Electronic Technology") and must not mix into sector caps.
    if sym in sp500_sectors and sp500_sectors[sym]:
        return sp500_sectors[sym]
    if mcp_sector and str(mcp_sector).strip():
        return str(mcp_sector).strip()
    return "Unknown"


def count_sectors(positions: Iterable[Mapping[str, Any]]) -> Counter:
    return Counter(p["sector"] for p in positions)


def would_breach_sector_cap(
    *,
    sector: str,
    current_counts: Mapping[str, int],
    max_per_sector: int,
    adding: bool = True,
) -> bool:
    count = int(current_counts.get(sector, 0))
    if adding:
        return count + 1 > max_per_sector
    return count > max_per_sector


def filter_by_sector_cap(
    candidates: Sequence[Mapping[str, Any]],
    *,
    held_sectors: Sequence[str],
    max_per_sector: int,
) -> list[dict]:
    counts: Counter = Counter(held_sectors)
    out: list[dict] = []
    for c in candidates:
        row = dict(c)
        sector = row["sector"]
        group = row.get("group", "new")
        if group == "new":
            if would_breach_sector_cap(
                sector=sector,
                current_counts=counts,
                max_per_sector=max_per_sector,
                adding=True,
            ):
                row["sector_cap_passed"] = False
                row["sector_cap_reason"] = (
                    f"sector {sector} already at {counts[sector]} (max {max_per_sector})"
                )
            else:
                row["sector_cap_passed"] = True
                row["sector_cap_reason"] = None
                counts[sector] += 1
        else:
            row["sector_cap_passed"] = True
            row["sector_cap_reason"] = None
        out.append(row)
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rules", default="risk_rules.json")
    p.add_argument("--sp500", default="data/universe/sp500.csv")
    p.add_argument("--etf-sectors", default="data/universe/etf_sectors.csv")
    p.add_argument("--candidates", required=True)
    p.add_argument("--held-sectors", default="")
    args = p.parse_args(argv)

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    max_per = rules["position_sizing"]["max_positions_per_sector"]
    sp500 = load_sp500_sectors(args.sp500)
    etf_map = load_etf_sectors(args.etf_sectors)
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))

    resolved = []
    for c in candidates:
        sector = c.get("sector") or resolve_sector(
            c["symbol"],
            asset_type=c.get("asset_type", "stock"),
            mcp_sector=c.get("mcp_sector"),
            sp500_sectors=sp500,
            etf_sectors=etf_map,
        )
        row = dict(c)
        row["sector"] = sector
        resolved.append(row)

    held = [s.strip() for s in args.held_sectors.split(",") if s.strip()]
    print(
        json.dumps(
            {
                "results": filter_by_sector_cap(
                    resolved, held_sectors=held, max_per_sector=max_per
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
