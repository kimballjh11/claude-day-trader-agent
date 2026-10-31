#!/usr/bin/env python3
"""Live order placement helpers (Milestone 10).

Refuses to build or accept place payloads unless execution.mode == live
and autonomy.phase >= 2. Actual MCP calls are made by Claude Code; this
module validates shape, classifies confirmations, and audits matches.

Field names are provisional until docs/mcp_tools.md is filled (VERIFY #2).
"""
from __future__ import annotations

import json
import math
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]


class LiveTradingDisabled(RuntimeError):
    """Raised when live placement is attempted in paper mode."""


def load_rules(path: Path | str | None = None) -> dict:
    return json.loads((Path(path) if path else ROOT / "risk_rules.json").read_text(encoding="utf-8"))


def assert_live_enabled(rules: Optional[Mapping[str, Any]] = None) -> None:
    rules = rules or load_rules()
    mode = rules.get("execution", {}).get("mode")
    phase = int(rules.get("autonomy", {}).get("phase", 0))
    if mode != "live" or phase < 2:
        raise LiveTradingDisabled(
            f"live trading disabled (mode={mode!r}, phase={phase}); "
            "the operator must flip risk_rules.json by hand (M11)"
        )


def agent_account_number(rules: Mapping[str, Any]) -> str:
    """Agent account number from the env var named in risk_rules.json (never committed)."""
    env_var = rules.get("account", {}).get("account_number_env_var", "RH_AGENT_ACCOUNT_NUMBER")
    value = os.environ.get(env_var, "").strip()
    if not value:
        raise ValueError(f"{env_var} is not set; cannot build a live order")
    return value


def build_market_buy(
    *,
    symbol: str,
    dollar_amount: float,
    rules: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Return a place_equity_order argument dict (provisional field names)."""
    rules = rules or load_rules()
    assert_live_enabled(rules)
    order_rules = rules["order_rules"]
    max_usd = float(rules["position_sizing"]["max_order_usd"])
    if dollar_amount <= 0:
        raise ValueError("dollar_amount must be positive")
    if dollar_amount > max_usd:
        raise ValueError(f"dollar_amount {dollar_amount} > max_order_usd {max_usd}")
    return {
        "account_number": agent_account_number(rules),
        "symbol": symbol.upper(),
        "side": "buy",
        "type": "market",
        "dollar_amount": f"{math.floor(float(dollar_amount) * 100) / 100:.2f}",
        "time_in_force": order_rules.get("time_in_force", "gfd"),
        "market_hours": "regular_hours",
        "ref_id": str(uuid.uuid4()),
    }


def build_market_sell(
    *,
    symbol: str,
    quantity: float,
    rules: Optional[Mapping[str, Any]] = None,
) -> dict:
    rules = rules or load_rules()
    assert_live_enabled(rules)
    order_rules = rules["order_rules"]
    # Robinhood takes quantity as a string, at most 6 decimals. Round down so a
    # sell never asks for more shares than are held.
    qty = math.floor(float(quantity) * 1_000_000) / 1_000_000
    if qty <= 0:
        raise ValueError("quantity must be positive")
    return {
        "account_number": agent_account_number(rules),
        "symbol": symbol.upper(),
        "side": "sell",
        "type": "market",
        "quantity": f"{qty:.6f}".rstrip("0").rstrip("."),
        "time_in_force": order_rules.get("time_in_force", "gfd"),
        "market_hours": "regular_hours",
        "ref_id": str(uuid.uuid4()),
    }


def for_review(payload: Mapping[str, Any]) -> dict:
    """review_equity_order rejects unknown fields and has no ref_id (verified
    schema), so drop it for previews. Whether place_equity_order accepts ref_id
    is still unverified (VERIFY #2)."""
    return {k: v for k, v in payload.items() if k != "ref_id"}


def classify_order_status(order: Mapping[str, Any]) -> dict:
    """Interpret get_equity_orders row / place response.

    Returns {state, code, detail} where state is one of:
    filled | confirmed | pending | pending_robinhood_approval | rejected | unknown
    """
    status = str(
        order.get("state")
        or order.get("status")
        or order.get("order_status")
        or ""
    ).lower()
    message = str(
        order.get("approval_message")
        or order.get("message")
        or order.get("reject_reason")
        or ""
    )

    held_tokens = ("approval", "pending_approval", "awaiting_approval", "held")
    if any(t in status for t in held_tokens) or any(t in message.lower() for t in ("approve", "approval")):
        return {
            "state": "pending_robinhood_approval",
            "code": "ROBINHOOD_APPROVAL_REQUIRED",
            "detail": message or status,
            "log_tag": "pending_robinhood_approval",
        }

    if status in ("filled", "completed", "executed"):
        return {"state": "filled", "code": None, "detail": status, "log_tag": "filled"}

    if status in ("confirmed", "submitted", "queued", "unconfirmed", "open", "pending"):
        # pending without approval language — needs second poll
        return {"state": "pending", "code": None, "detail": status, "log_tag": "pending"}

    if status in ("rejected", "canceled", "cancelled", "failed"):
        return {"state": "rejected", "code": "ORDER_REJECTED", "detail": message or status, "log_tag": "rejected"}

    return {"state": "unknown", "code": "ORDER_NOT_CONFIRMED", "detail": status or "empty_status", "log_tag": "unknown"}


def confirm_after_polls(polls: list[Mapping[str, Any]]) -> dict:
    """Given 1–2 get_equity_orders snapshots for one order id, decide outcome."""
    if not polls:
        return {
            "ok": False,
            "code": "ORDER_NOT_CONFIRMED",
            "state": "unknown",
            "detail": "no order snapshots",
        }
    last = classify_order_status(polls[-1])
    if last["state"] == "filled":
        return {"ok": True, "code": None, **last}
    if last["state"] == "pending_robinhood_approval":
        return {"ok": False, **last}
    if last["state"] == "rejected":
        return {"ok": False, **last}
    if last["state"] == "pending" and len(polls) >= 2:
        # still pending after two checks
        return {
            "ok": False,
            "code": "ORDER_NOT_CONFIRMED",
            "state": "pending",
            "detail": last["detail"],
            "log_tag": "unconfirmed_after_polls",
        }
    if last["state"] == "pending":
        return {"ok": False, "code": None, "state": "pending", "detail": "awaiting_second_poll", "log_tag": "pending"}
    return {"ok": False, "code": "ORDER_NOT_CONFIRMED", **last}


def _order_id(o: Mapping[str, Any]) -> str:
    return str(o.get("order_id") or o.get("id") or "")


def orders_match_log(
    *,
    placed: list[Mapping[str, Any]],
    broker_orders: list[Mapping[str, Any]],
) -> list[dict]:
    """Live audit: every placed log row must appear in broker history by order id,
    with the same symbol and side. A placed row without an order id is itself a
    violation (the place response was never recorded)."""
    violations = []
    broker_by_id = {_order_id(o): o for o in broker_orders if _order_id(o)}
    for p in placed:
        sym = (p.get("symbol") or "").upper()
        book = p.get("book", "claude")
        oid = _order_id(p)
        if not oid:
            violations.append(
                {"code": "LIVE_ORDER_NO_ID", "detail": f"placed {sym} has no order_id in the log", "book": book}
            )
            continue
        broker = broker_by_id.get(oid)
        if broker is None:
            violations.append(
                {"code": "LIVE_ORDER_MISSING", "detail": f"order {oid} ({sym}) not found in broker order history", "book": book}
            )
            continue
        b_sym = (broker.get("symbol") or broker.get("instrument") or "").upper()
        b_side = str(broker.get("side") or "").lower()
        p_side = str(p.get("side") or "").lower()
        if (b_sym and b_sym != sym) or (b_side and p_side and b_side != p_side):
            violations.append(
                {
                    "code": "LIVE_ORDER_MISMATCH",
                    "detail": f"order {oid}: log {sym} {p_side} vs broker {b_sym} {b_side}",
                    "book": book,
                }
            )
    return violations


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-buy")
    b.add_argument("--symbol", required=True)
    b.add_argument("--dollar-amount", type=float, required=True)
    b.add_argument("--for-review", action="store_true", help="omit ref_id (review_equity_order args)")

    s = sub.add_parser("build-sell")
    s.add_argument("--symbol", required=True)
    s.add_argument("--quantity", type=float, required=True)
    s.add_argument("--for-review", action="store_true", help="omit ref_id (review_equity_order args)")

    c = sub.add_parser("classify")
    c.add_argument("--order-json", required=True, help="path to one order JSON object")

    args = p.parse_args()
    try:
        if args.cmd == "build-buy":
            payload = build_market_buy(symbol=args.symbol, dollar_amount=args.dollar_amount)
            print(json.dumps(for_review(payload) if args.for_review else payload))
        elif args.cmd == "build-sell":
            payload = build_market_sell(symbol=args.symbol, quantity=args.quantity)
            print(json.dumps(for_review(payload) if args.for_review else payload))
        elif args.cmd == "classify":
            order = json.loads(Path(args.order_json).read_text(encoding="utf-8"))
            print(json.dumps(classify_order_status(order)))
    except LiveTradingDisabled as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
