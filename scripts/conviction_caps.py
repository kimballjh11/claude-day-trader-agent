#!/usr/bin/env python3
"""Enforce conviction caps from risk_rules.json (Section 7.4). Never raises conviction."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

RANK = {"high": 3, "medium": 2, "low": 1}


def lower_of(a: str, b: str) -> str:
    if a not in RANK or b not in RANK:
        raise ValueError(f"invalid conviction {a!r} / {b!r}")
    return a if RANK[a] <= RANK[b] else b


def apply_caps(
    *,
    conviction: str,
    asset_type: str,
    macro_regime: Optional[str],
    ahead_of_earnings: bool,
    rules: Mapping[str, Any],
) -> dict:
    if conviction not in RANK:
        raise ValueError(f"invalid conviction {conviction!r}")

    caps = rules.get("conviction_caps", {})
    applied: list[str] = []
    out = conviction

    if asset_type.lower() == "etf":
        etf_max = caps.get("etf_max_conviction", "medium")
        new = lower_of(out, etf_max)
        if new != out:
            applied.append("etf_max_conviction")
        out = new

    regime_caps = caps.get("regime_caps") or {}
    if macro_regime and macro_regime in regime_caps:
        new = lower_of(out, regime_caps[macro_regime])
        if new != out:
            applied.append(f"regime:{macro_regime}")
        out = new

    if ahead_of_earnings:
        earn_max = caps.get("ahead_of_earnings_max_conviction", "medium")
        new = lower_of(out, earn_max)
        if new != out:
            applied.append("ahead_of_earnings")
        out = new

    return {
        "conviction_in": conviction,
        "conviction_out": out,
        "caps_applied": applied,
        "changed": out != conviction,
    }


def apply_caps_to_proposals(
    proposals: Sequence[Mapping[str, Any]],
    rules: Mapping[str, Any],
) -> list[dict]:
    results = []
    for p in proposals:
        row = dict(p)
        if p.get("action") not in ("buy", "add") or not p.get("conviction"):
            row["conviction_caps"] = {"skipped": True}
            results.append(row)
            continue
        capped = apply_caps(
            conviction=p["conviction"],
            asset_type=p.get("asset_type", "stock"),
            macro_regime=p.get("macro_regime"),
            ahead_of_earnings=bool(p.get("ahead_of_earnings", False)),
            rules=rules,
        )
        row["conviction"] = capped["conviction_out"]
        row["conviction_caps"] = capped
        results.append(row)
    return results


def load_proposals(path: Path) -> list[dict]:
    """Read a JSON array or JSONL file of proposals."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rules", default="risk_rules.json")
    p.add_argument("--proposals", required=True,
                   help="JSON array or JSONL (one proposal per line), e.g. state/pending_proposals.jsonl")
    p.add_argument("--write-jsonl", default="",
                   help="write capped proposals here as JSONL (may be the same file as --proposals)")
    args = p.parse_args(argv)

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    proposals = load_proposals(Path(args.proposals))
    results = apply_caps_to_proposals(proposals, rules)
    if args.write_jsonl:
        out = Path(args.write_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
        tmp.replace(out)
    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
