#!/usr/bin/env python3
"""Rule-violation and reconciliation checks (Section 10.5)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]


def reconcile_ledger(ledger: dict, tol: float = 0.02) -> Optional[str]:
    """Self-consistency checks, then equity vs the last equity_history mark.

    Phase B runs audit right after `paper_broker.py mark`, so the computed
    equity must equal the newest history entry (to rounding). Ledgers with no
    history (e.g. unit-test fixtures) skip the equity check.
    """
    if float(ledger["cash_settled_usd"]) < -tol:
        return "negative_settled_cash"
    for u in ledger.get("cash_unsettled", []):
        if float(u.get("amount_usd", 0)) < 0 or not u.get("settles_on"):
            return "bad_unsettled_entry"
    for p in ledger.get("positions", []):
        if float(p["quantity"]) <= 0:
            return f"bad_quantity_{p.get('symbol')}"
        if float(p.get("avg_cost_usd") or 0) <= 0:
            return f"bad_avg_cost_{p.get('symbol')}"

    hist = ledger.get("equity_history") or []
    if hist:
        unsettled = sum(float(u.get("amount_usd", 0)) for u in ledger.get("cash_unsettled", []))
        pos = sum(
            float(p["quantity"]) * float(p.get("last_price_usd", p["avg_cost_usd"]))
            for p in ledger.get("positions", [])
        )
        computed = round(float(ledger["cash_settled_usd"]) + unsettled + pos, 2)
        marked = float(hist[-1]["equity_usd"])
        if abs(computed - marked) > tol:
            return f"equity_mismatch computed={computed} last_mark={marked}"
    return None


def audit_session(
    *,
    rules: dict,
    fills: list[dict],
    ledgers: dict[str, dict],
    mode: Optional[str] = None,
    broker_orders: Optional[list[dict]] = None,
) -> list[dict]:
    """Return list of violation dicts {code, detail, book?}."""
    violations: list[dict] = []
    mode = mode or rules["execution"]["mode"]
    sizing = rules["position_sizing"]

    if mode == "paper":
        for f in fills:
            if f.get("placed_real_order"):
                violations.append(
                    {
                        "code": "REAL_ORDER_IN_PAPER",
                        "detail": f"real order while paper: {f.get('symbol')}",
                        "book": f.get("book"),
                    }
                )
    else:
        # Live: every real place must appear in broker history
        placed = [f for f in fills if f.get("placed_real_order") or f.get("mode") == "live"]
        if broker_orders is not None and placed:
            from live_orders import orders_match_log

            violations.extend(orders_match_log(placed=placed, broker_orders=broker_orders))

    for f in fills:
        book = f.get("book")
        amt = f.get("amount_usd") or f.get("dollar_amount")
        if amt is not None and float(amt) > float(sizing["max_order_usd"]) + 1e-9:
            violations.append(
                {
                    "code": "MAX_ORDER",
                    "detail": f"{f.get('symbol')} amount {amt} > max_order_usd",
                    "book": book,
                }
            )
        if f.get("side") == "buy" and f.get("halted"):
            violations.append(
                {
                    "code": "BUY_DURING_HALT",
                    "detail": f"buy of {f.get('symbol')} during loss halt",
                    "book": book,
                }
            )
        if f.get("excluded_symbol"):
            violations.append(
                {
                    "code": "EXCLUDED_SYMBOL",
                    "detail": f"bought excluded {f.get('symbol')}",
                    "book": book,
                }
            )

    for book, ledger in ledgers.items():
        positions = ledger.get("positions", [])
        if len(positions) > int(sizing["max_concurrent_positions"]):
            violations.append(
                {
                    "code": "MAX_POSITIONS",
                    "detail": f"{book} has {len(positions)} positions",
                    "book": book,
                }
            )
        # sector counts
        from collections import Counter

        counts = Counter(p.get("sector", "Unknown") for p in positions)
        max_sec = int(sizing["max_positions_per_sector"])
        for sector, n in counts.items():
            if n > max_sec:
                violations.append(
                    {
                        "code": "SECTOR_CAP",
                        "detail": f"{book} sector {sector} count {n}",
                        "book": book,
                    }
                )

        equity = float(ledger.get("cash_settled_usd", 0))
        unsettled = sum(u.get("amount_usd", 0) for u in ledger.get("cash_unsettled", []))
        pos_val = sum(
            float(p["quantity"]) * float(p.get("last_price_usd", p["avg_cost_usd"]))
            for p in positions
        )
        total = equity + unsettled + pos_val
        floor = float(sizing["min_cash_buffer_pct"]) * total if total else 0
        # Only flag floor if there were buys this session
        if any(f.get("book") == book and f.get("side") == "buy" for f in fills):
            if float(ledger.get("cash_settled_usd", 0)) + 1e-9 < floor:
                # Use settled-only check loosely: cash below floor of equity
                if float(ledger["cash_settled_usd"]) < float(sizing["min_cash_buffer_pct"]) * total - 0.01:
                    violations.append(
                        {
                            "code": "CASH_FLOOR",
                            "detail": f"{book} settled cash below floor after buys",
                            "book": book,
                        }
                    )

        bad = reconcile_ledger(ledger)
        if bad:
            violations.append({"code": "LEDGER_INVALID", "detail": bad, "book": book})

    # new per session
    for book in ledgers:
        new_buys = [
            f
            for f in fills
            if f.get("book") == book and f.get("side") == "buy" and f.get("is_new_position")
        ]
        if len(new_buys) > int(sizing["max_new_positions_per_session"]):
            violations.append(
                {
                    "code": "MAX_NEW_SESSION",
                    "detail": f"{book} {len(new_buys)} new buys this session",
                    "book": book,
                }
            )

    return violations


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rules", default="risk_rules.json")
    p.add_argument("--fills", required=True, help="JSON array of fill records")
    p.add_argument("--ledgers", nargs="+", required=True, help="paper ledger paths")
    args = p.parse_args(argv)

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    fills = json.loads(Path(args.fills).read_text(encoding="utf-8"))
    ledgers = {}
    for path in args.ledgers:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        ledgers[data.get("book", Path(path).stem)] = data

    violations = audit_session(rules=rules, fills=fills, ledgers=ledgers)
    out = {"ok": len(violations) == 0, "violations": violations}
    # Persist for dashboard graduation (append session hits)
    log_path = ROOT / "state" / "violations.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if violations:
        with log_path.open("a", encoding="utf-8") as f:
            for v in violations:
                f.write(json.dumps(v) + "\n")
    print(json.dumps(out))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
