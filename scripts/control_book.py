#!/usr/bin/env python3
"""Build deterministic control-book proposals (Section 7.8). No Claude."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

# Local imports when run as script
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import conviction_caps  # noqa: E402


def build_control_proposals(
    researched: Sequence[dict[str, Any]],
    rules: dict,
    *,
    as_of: str,
) -> list[dict]:
    """Same researched list Claude saw; every candidate medium; buy or hold."""
    if not rules.get("control_book", {}).get("enabled", True):
        return []

    fixed = rules["control_book"].get("fixed_conviction", "medium")
    out: list[dict] = []
    for c in researched:
        symbol = c["symbol"].upper()
        is_holding = bool(c.get("is_holding"))
        asset_type = c.get("asset_type", "stock")
        action = "hold" if is_holding else "buy"
        proposal = {
            "proposal_id": f"{as_of.replace('-', '')}-{symbol}-control",
            "symbol": symbol,
            "asset_type": asset_type,
            "action": action,
            "conviction": fixed if action == "buy" else c.get("conviction", fixed),
            "thesis_price": c.get("thesis_price", c.get("close")),
            "catalyst": None,
            "counter_case": None,
            "invalidation_condition": None,
            "signals_fired": c.get("signals_fired", []),
            "mom_12_1": c.get("mom_12_1"),
            "ret_60d": c.get("ret_60d"),
            "macro_regime": c.get("macro_regime"),
            "risk_flags": list(c.get("risk_flags") or []),
            "sources": [],
            "risk_verdict": "control_book_no_risk_manager",
            "book": "control",
            "thesis_exits": False,
        }
        out.append(proposal)

    # Apply ETF / regime caps (never raises)
    capped = conviction_caps.apply_caps_to_proposals(
        [
            {
                **p,
                "ahead_of_earnings": False,
            }
            for p in out
        ],
        rules,
    )
    return capped


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rules", default="risk_rules.json")
    p.add_argument("--researched", required=True, help="JSON array from Phase A shortlist")
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", default="state/control_proposals.jsonl")
    args = p.parse_args(argv)

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    researched = json.loads(Path(args.researched).read_text(encoding="utf-8"))
    proposals = build_control_proposals(researched, rules, as_of=args.as_of)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for row in proposals:
            f.write(json.dumps(row) + "\n")

    print(json.dumps({"ok": True, "count": len(proposals), "path": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
