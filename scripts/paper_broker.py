#!/usr/bin/env python3
"""Simulated fills, settlement, and mark-to-market for paper ledgers."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT / "paper"


def _ledger_path(book: str) -> Path:
    return PAPER_DIR / f"{book}.json"


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load(book: str) -> dict:
    path = _ledger_path(book)
    if not path.exists():
        raise FileNotFoundError(f"ledger missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(ledger: dict) -> None:
    if "cash_settled_usd" not in ledger or "positions" not in ledger:
        raise ValueError("ledger missing required fields")
    if ledger["cash_settled_usd"] < -0.001:
        raise ValueError("negative settled cash")
    for p in ledger["positions"]:
        if p["quantity"] <= 0:
            raise ValueError(f"non-positive quantity for {p.get('symbol')}")


def _equity(ledger: dict) -> float:
    unsettled = sum(u["amount_usd"] for u in ledger.get("cash_unsettled", []))
    pos = sum(p["quantity"] * p.get("last_price_usd", p["avg_cost_usd"]) for p in ledger["positions"])
    return round(ledger["cash_settled_usd"] + unsettled + pos, 2)


def _next_trading_day(d: date, holidays: set[str]) -> date:
    cur = d + timedelta(days=1)
    while cur.weekday() >= 5 or cur.isoformat() in holidays:
        cur += timedelta(days=1)
    return cur


def _holidays() -> set[str]:
    path = ROOT / "data" / "market_holidays.json"
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("closed") or [])


def cmd_init(book: str, capital: float, d: str) -> dict:
    path = _ledger_path(book)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing ledger {path}")
    ledger = {
        "book": book,
        "starting_capital_usd": capital,
        "inception_date": d,
        "cash_settled_usd": capital,
        "cash_unsettled": [],
        "positions": [],
        "closed_trades": [],
        "equity_history": [{"date": d, "run": "init", "equity_usd": capital}],
    }
    _validate(ledger)
    _atomic_write(path, ledger)
    return ledger


def cmd_settle(book: str, d: str) -> dict:
    ledger = _load(book)
    _validate(ledger)
    keep = []
    for u in ledger.get("cash_unsettled", []):
        if u["settles_on"] <= d:
            ledger["cash_settled_usd"] = round(ledger["cash_settled_usd"] + u["amount_usd"], 2)
        else:
            keep.append(u)
    ledger["cash_unsettled"] = keep
    _validate(ledger)
    _atomic_write(_ledger_path(book), ledger)
    return ledger


def cmd_fill_buy(
    book: str,
    symbol: str,
    dollar_amount: float,
    price: float,
    d: str,
    *,
    asset_type: str = "stock",
    sector: str = "Unknown",
    conviction: str = "medium",
    stop_pct: float = 0.07,
    proposal_id: str = "",
    min_cash_buffer_pct: float = 0.15,
) -> dict:
    ledger = _load(book)
    _validate(ledger)
    if price <= 0 or dollar_amount <= 0:
        raise ValueError("price and dollar_amount must be positive")

    equity = _equity(ledger)
    floor = min_cash_buffer_pct * equity
    if ledger["cash_settled_usd"] - dollar_amount < floor - 1e-9:
        raise ValueError(
            f"insufficient settled cash after floor: settled={ledger['cash_settled_usd']} "
            f"order={dollar_amount} floor={floor}"
        )

    qty = dollar_amount / price
    ledger["cash_settled_usd"] = round(ledger["cash_settled_usd"] - dollar_amount, 2)

    existing = next((p for p in ledger["positions"] if p["symbol"] == symbol), None)
    if existing:
        new_qty = existing["quantity"] + qty
        existing["avg_cost_usd"] = round(
            (existing["avg_cost_usd"] * existing["quantity"] + price * qty) / new_qty, 6
        )
        existing["quantity"] = new_qty
        existing["conviction"] = conviction
        existing["last_price_usd"] = price
        existing["stop_pct"] = stop_pct
        existing["stop_price_usd"] = round(existing["avg_cost_usd"] * (1 - stop_pct), 4)
    else:
        ledger["positions"].append(
            {
                "symbol": symbol,
                "asset_type": asset_type,
                "sector": sector,
                "quantity": qty,
                "avg_cost_usd": price,
                "entry_date": d,
                "entry_proposal_id": proposal_id or f"{d.replace('-', '')}-{symbol}-{book}",
                "conviction": conviction,
                "stop_pct": stop_pct,
                "stop_price_usd": round(price * (1 - stop_pct), 4),
                "take_profit_tiers_hit": [],
                "last_price_usd": price,
                "last_marked_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    _validate(ledger)
    _atomic_write(_ledger_path(book), ledger)
    return ledger


def cmd_fill_sell(
    book: str,
    symbol: str,
    quantity: float,
    price: float,
    d: str,
    reason: str,
    *,
    take_profit_tier: Optional[float] = None,
) -> dict:
    ledger = _load(book)
    _validate(ledger)
    pos = next((p for p in ledger["positions"] if p["symbol"] == symbol), None)
    if pos is None:
        raise ValueError(f"no position in {symbol}")
    if quantity <= 0 or quantity > pos["quantity"] + 1e-12:
        raise ValueError(f"invalid sell qty {quantity} vs held {pos['quantity']}")

    proceeds = round(quantity * price, 2)
    realized = round((price - pos["avg_cost_usd"]) * quantity, 2)
    settles = _next_trading_day(date.fromisoformat(d), _holidays()).isoformat()
    ledger["cash_unsettled"].append({"amount_usd": proceeds, "settles_on": settles})

    trade = {
        "symbol": symbol,
        "entry_date": pos["entry_date"],
        "exit_date": d,
        "quantity": quantity,
        "avg_cost_usd": pos["avg_cost_usd"],
        "exit_price_usd": price,
        "realized_usd": realized,
        "exit_reason": reason,
        "partial": True,
    }
    if take_profit_tier is not None:
        trade["take_profit_tier"] = float(take_profit_tier)
        hit = list(pos.get("take_profit_tiers_hit") or [])
        if float(take_profit_tier) not in hit:
            hit.append(float(take_profit_tier))
        pos["take_profit_tiers_hit"] = hit

    remaining = pos["quantity"] - quantity
    if remaining <= 1e-12:
        trade["partial"] = False
        ledger["positions"] = [p for p in ledger["positions"] if p["symbol"] != symbol]
    else:
        pos["quantity"] = remaining
        pos["last_price_usd"] = price

    ledger.setdefault("closed_trades", []).append(trade)

    _validate(ledger)
    _atomic_write(_ledger_path(book), ledger)
    return ledger


def cmd_mark(book: str, prices: dict[str, float], d: str, run: str) -> dict:
    ledger = _load(book)
    _validate(ledger)
    now = datetime.now(timezone.utc).isoformat()
    for p in ledger["positions"]:
        if p["symbol"] in prices:
            p["last_price_usd"] = float(prices[p["symbol"]])
            p["last_marked_at"] = now
    eq = _equity(ledger)
    ledger["equity_history"].append({"date": d, "run": run, "equity_usd": eq})
    _validate(ledger)
    _atomic_write(_ledger_path(book), ledger)
    return ledger


def cmd_benchmark(spy_price: float, d: str, run: str, *, inception_spy: Optional[float] = None) -> dict:
    """Mark SPY-indexed $1000 book. Indexed equity = 1000 * spy_price / inception_spy."""
    path = PAPER_DIR / "benchmark.json"
    if path.exists():
        bench = json.loads(path.read_text(encoding="utf-8"))
    else:
        if inception_spy is None or inception_spy <= 0:
            raise ValueError("first benchmark mark requires --inception-spy > 0")
        bench = {
            "starting_capital_usd": 1000.0,
            "inception_date": d,
            "inception_spy_price": float(inception_spy),
            "equity_history": [],
        }
    base = float(bench.get("inception_spy_price") or 0)
    if inception_spy is not None and inception_spy > 0:
        if base <= 0:
            bench["inception_spy_price"] = float(inception_spy)
            base = float(inception_spy)
        elif abs(base - float(inception_spy)) > 1e-9 and not bench.get("equity_history"):
            bench["inception_spy_price"] = float(inception_spy)
            base = float(inception_spy)
    if base <= 0:
        raise ValueError("benchmark missing inception_spy_price; pass --inception-spy")
    if spy_price <= 0:
        raise ValueError("spy price must be positive")
    indexed = round(1000.0 * float(spy_price) / base, 2)
    bench["last_spy_price"] = float(spy_price)
    bench["indexed_equity_usd"] = indexed
    bench.setdefault("equity_history", []).append(
        {"date": d, "run": run, "equity_usd": indexed, "spy_price": float(spy_price)}
    )
    _atomic_write(path, bench)
    return bench


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init")
    i.add_argument("--book", required=True, choices=["claude", "control"])
    i.add_argument("--capital", type=float, default=1000.0)
    i.add_argument("--date", required=True)

    s = sub.add_parser("settle")
    s.add_argument("--book", required=True)
    s.add_argument("--date", required=True)

    f = sub.add_parser("fill")
    f.add_argument("--book", required=True)
    f.add_argument("--side", required=True, choices=["buy", "sell"])
    f.add_argument("--symbol", required=True)
    f.add_argument("--dollar-amount", type=float)
    f.add_argument("--quantity", type=float)
    f.add_argument("--price", type=float, required=True)
    f.add_argument("--date", required=True)
    f.add_argument("--reason", default="")
    f.add_argument("--sector", default="Unknown")
    f.add_argument("--asset-type", default="stock")
    f.add_argument("--conviction", default="medium")
    f.add_argument("--stop-pct", type=float, default=0.07)
    f.add_argument("--proposal-id", default="")
    f.add_argument("--min-cash-buffer-pct", type=float, default=0.15)
    f.add_argument(
        "--take-profit-tier",
        type=float,
        default=None,
        help="gain_pct tier just fired (e.g. 0.15); recorded on position + trade",
    )

    m = sub.add_parser("mark")
    m.add_argument("--book", required=True)
    m.add_argument("--prices", required=True, help="JSON file symbol->price")
    m.add_argument("--date", required=True)
    m.add_argument("--run", required=True)

    b = sub.add_parser("benchmark", help="Update paper/benchmark.json SPY-indexed $1000 line")
    b.add_argument("--spy-price", type=float, required=True)
    b.add_argument("--date", required=True)
    b.add_argument("--run", required=True)
    b.add_argument(
        "--inception-spy",
        type=float,
        default=None,
        help="SPY price at inception (required on first mark)",
    )

    args = p.parse_args(argv)
    try:
        if args.cmd == "init":
            ledger = cmd_init(args.book, args.capital, args.date)
            print(json.dumps({"ok": True, "equity_usd": _equity(ledger), "book": ledger["book"]}))
        elif args.cmd == "settle":
            ledger = cmd_settle(args.book, args.date)
            print(json.dumps({"ok": True, "equity_usd": _equity(ledger), "book": ledger["book"]}))
        elif args.cmd == "fill":
            if args.side == "buy":
                if args.dollar_amount is None:
                    raise SystemExit("--dollar-amount required for buy")
                ledger = cmd_fill_buy(
                    args.book,
                    args.symbol.upper(),
                    args.dollar_amount,
                    args.price,
                    args.date,
                    asset_type=args.asset_type,
                    sector=args.sector,
                    conviction=args.conviction,
                    stop_pct=args.stop_pct,
                    proposal_id=args.proposal_id,
                    min_cash_buffer_pct=args.min_cash_buffer_pct,
                )
            else:
                if args.quantity is None:
                    raise SystemExit("--quantity required for sell")
                ledger = cmd_fill_sell(
                    args.book,
                    args.symbol.upper(),
                    args.quantity,
                    args.price,
                    args.date,
                    args.reason or "manual",
                    take_profit_tier=args.take_profit_tier,
                )
            print(json.dumps({"ok": True, "equity_usd": _equity(ledger), "book": ledger["book"]}))
        elif args.cmd == "mark":
            prices = json.loads(Path(args.prices).read_text(encoding="utf-8"))
            ledger = cmd_mark(args.book, prices, args.date, args.run)
            print(json.dumps({"ok": True, "equity_usd": _equity(ledger), "book": ledger["book"]}))
        elif args.cmd == "benchmark":
            bench = cmd_benchmark(
                args.spy_price, args.date, args.run, inception_spy=args.inception_spy
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "equity_usd": bench["indexed_equity_usd"],
                        "book": "benchmark",
                        "spy_price": bench["last_spy_price"],
                    }
                )
            )
        else:
            raise SystemExit(f"unknown cmd {args.cmd}")
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
