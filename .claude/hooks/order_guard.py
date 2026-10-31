#!/usr/bin/env python3
"""Fail-closed PreToolUse guard for Robinhood place/cancel tools.

Reads tool-call JSON from stdin and risk_rules.json from disk.
Any exception, missing field, or unparseable value → deny (exit 2).
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Exit 0 = allow; exit 2 = deny (Claude Code hook convention).


def _deny(msg: str) -> int:
    print(f"ORDER GUARD DENY: {msg}", file=sys.stderr)
    return 2


def _project_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    # hooks/order_guard.py -> .claude -> repo root
    return Path(__file__).resolve().parents[2]


def _load_rules(root: Path) -> dict:
    path = root / "risk_rules.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_exclusions(root: Path) -> set[str]:
    path = root / "data" / "universe" / "etf_exclusions.csv"
    if not path.exists():
        return set()
    out = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip().upper()
            if sym:
                out.add(sym)
    return out


def _load_holidays(root: Path) -> set[str]:
    path = root / "data" / "market_holidays.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("closed") or [])


def _parse_tool_input(raw: dict) -> dict:
    """Normalize Claude Code hook payload shapes into a flat order dict."""
    # Common shapes: {"tool_input": {...}}, {"input": {...}}, or the order itself
    if "tool_input" in raw and isinstance(raw["tool_input"], dict):
        return raw["tool_input"]
    if "input" in raw and isinstance(raw["input"], dict):
        return raw["input"]
    if "arguments" in raw and isinstance(raw["arguments"], dict):
        return raw["arguments"]
    return raw


def _in_order_window(now_et: datetime, window: list[str]) -> bool:
    start_s, end_s = window[0], window[1]
    sh, sm = map(int, start_s.split(":"))
    eh, em = map(int, end_s.split(":"))
    minutes = now_et.hour * 60 + now_et.minute
    return (sh * 60 + sm) <= minutes < (eh * 60 + em)


ALLOWED_TOOL_SUFFIX = "__place_equity_order"
REGULAR_HOURS = "regular_hours"


def evaluate(payload: dict, rules: dict, exclusions: set[str], holidays: set[str],
             now_et: datetime | None = None,
             agent_account: str | None = None) -> tuple[bool, str]:
    """Return (allowed, reason). False means deny.

    agent_account is the agent account number (from the env var named in
    risk_rules.json account.account_number_env_var). Missing → deny.
    """
    try:
        tool_name = str(payload.get("tool_name") or "")
        if tool_name and not tool_name.endswith(ALLOWED_TOOL_SUFFIX):
            return False, f"tool {tool_name} not permitted (only place_equity_order; cancels stay denied)"

        execution = rules["execution"]
        autonomy = rules["autonomy"]
        order_rules = rules["order_rules"]
        sizing = rules["position_sizing"]

        if execution.get("mode") != "live" or int(autonomy.get("phase", 0)) < 2:
            return False, "execution.mode is not live or autonomy.phase < 2"

        now = now_et or datetime.now(ZoneInfo("America/New_York"))
        if now.weekday() >= 5:
            return False, "weekend"
        day = now.date().isoformat()
        if day in holidays:
            return False, f"market holiday {day}"

        window = order_rules.get("allowed_order_window_et", ["09:30", "11:00"])
        if not _in_order_window(now, window):
            return False, f"outside order window ET {window}"

        order = _parse_tool_input(payload)
        # Field names VERIFY against docs/mcp_tools.md — accept common aliases
        order_type = (order.get("type") or order.get("order_type") or "").lower()
        if order_type not in {t.lower() for t in order_rules.get("allowed_order_types", ["market"])}:
            return False, f"order type {order_type!r} not allowed"

        tif = (order.get("time_in_force") or order.get("tif") or "").lower()
        if tif and tif != str(order_rules.get("time_in_force", "gfd")).lower():
            return False, f"time_in_force {tif!r} not allowed"

        if order_rules.get("regular_hours_only", True):
            market_hours = str(order.get("market_hours") or REGULAR_HOURS).lower()
            if order.get("extended_hours") or market_hours != REGULAR_HOURS:
                return False, f"market_hours {market_hours!r} not allowed (regular_hours only)"

        if not agent_account:
            return False, "agent account number not configured (env var unset)"
        account = str(order.get("account_number") or "")
        if account != str(agent_account):
            return False, "account_number is not the agent account"

        side = (order.get("side") or "").lower()
        if side not in ("buy", "sell"):
            return False, f"side {side!r} must be buy or sell"

        symbol = (order.get("symbol") or order.get("instrument") or "").upper()
        if not symbol:
            return False, "missing symbol"

        if symbol in exclusions:
            return False, f"symbol {symbol} in etf_exclusions"

        asset = (order.get("asset_type") or order.get("instrument_type") or "equity").lower()
        if asset in ("option", "options", "crypto", "cryptocurrency"):
            return False, f"asset_type {asset} not allowed"

        if side == "buy":
            if order_rules.get("buys_must_use_dollar_amount", True):
                if "dollar_amount" not in order and "amount" not in order:
                    return False, "buy missing dollar_amount"
                if order.get("quantity") is not None:
                    return False, "buy must use dollar_amount only, not quantity"
            amt = order.get("dollar_amount", order.get("amount"))
            if amt is not None:
                amt_f = float(amt)
                if amt_f <= 0:
                    return False, f"dollar_amount {amt_f} must be positive"
                max_usd = float(sizing["max_order_usd"])
                if amt_f > max_usd:
                    return False, f"dollar_amount {amt_f} > max_order_usd {max_usd}"
        else:
            qty = order.get("quantity")
            if qty is None or float(qty) <= 0:
                return False, "sell must use a positive quantity"
            if order.get("dollar_amount") is not None or order.get("amount") is not None:
                return False, "sell must use quantity only, not dollar_amount"

        return True, "ok"
    except Exception as e:
        return False, f"guard exception: {e}"


def main() -> int:
    try:
        raw_text = sys.stdin.read()
        if not raw_text.strip():
            return _deny("empty stdin")
        payload = json.loads(raw_text)
    except Exception as e:
        return _deny(f"unparseable stdin: {e}")

    try:
        root = _project_root()
        rules = _load_rules(root)
        exclusions = _load_exclusions(root)
        holidays = _load_holidays(root)
        env_var = rules.get("account", {}).get("account_number_env_var", "RH_AGENT_ACCOUNT_NUMBER")
        agent_account = os.environ.get(env_var, "").strip() or None
        ok, reason = evaluate(payload, rules, exclusions, holidays, agent_account=agent_account)
    except Exception as e:
        return _deny(f"setup failure: {e}")

    if not ok:
        return _deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
