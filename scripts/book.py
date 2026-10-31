#!/usr/bin/env python3
"""Unified portfolio access — same schema for paper ledger or live account."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]


def _paper_path(book: str) -> Path:
    return ROOT / "paper" / f"{book}.json"


def load_paper(book: str) -> dict:
    path = _paper_path(book)
    data = json.loads(path.read_text(encoding="utf-8"))
    return normalize_ledger(data, mode="paper")


def normalize_ledger(raw: dict, *, mode: str = "paper") -> dict:
    """Canonical book schema used by dashboard builders and Phase B."""
    unsettled = sum(u.get("amount_usd", 0) for u in raw.get("cash_unsettled", []))
    positions = []
    for p in raw.get("positions", []):
        last = float(p.get("last_price_usd", p.get("avg_cost_usd", 0)))
        qty = float(p["quantity"])
        positions.append(
            {
                "symbol": p["symbol"],
                "asset_type": p.get("asset_type", "stock"),
                "sector": p.get("sector", "Unknown"),
                "quantity": qty,
                "avg_cost_usd": float(p["avg_cost_usd"]),
                "last_price_usd": last,
                "market_value_usd": round(qty * last, 2),
                "entry_date": p.get("entry_date"),
                "conviction": p.get("conviction"),
                "stop_pct": p.get("stop_pct"),
                "stop_price_usd": p.get("stop_price_usd"),
                "take_profit_tiers_hit": list(p.get("take_profit_tiers_hit") or []),
                "entry_proposal_id": p.get("entry_proposal_id"),
            }
        )
    cash_settled = float(raw.get("cash_settled_usd", 0))
    equity = round(cash_settled + unsettled + sum(p["market_value_usd"] for p in positions), 2)
    return {
        "book": raw.get("book"),
        "mode": mode,
        "starting_capital_usd": float(raw.get("starting_capital_usd", 0)),
        "inception_date": raw.get("inception_date"),
        "cash_settled_usd": cash_settled,
        "cash_unsettled_usd": round(unsettled, 2),
        "equity_usd": equity,
        "positions": positions,
        "closed_trades": list(raw.get("closed_trades") or []),
        "equity_history": list(raw.get("equity_history") or []),
    }


def map_live_mcp_to_ledger(
    *,
    portfolio: Mapping[str, Any],
    positions: list[Mapping[str, Any]],
    book: str = "claude",
    starting_capital_usd: float = 1000.0,
    inception_date: Optional[str] = None,
    sector_by_symbol: Optional[Mapping[str, str]] = None,
    account: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Map MCP get_portfolio + get_accounts + get_equity_positions into a
    paper-compatible ledger dict.

    Verified (docs/verified.md VERIFY #7): get_portfolio -> cash (string);
    get_accounts -> unsettled_funds. Never sized from buying_power. Whether
    portfolio.cash already includes unsettled funds is unverified, so settled
    cash = cash - unsettled (conservative: can only understate settled cash).
    Position field names are still provisional (VERIFY #2).
    """
    sector_by_symbol = sector_by_symbol or {}
    if portfolio.get("settled_cash") is not None:
        cash = float(portfolio["settled_cash"])
        unsettled = float(portfolio.get("unsettled_cash") or 0)
    else:
        if portfolio.get("cash") is None:
            raise ValueError("get_portfolio has no cash field; refusing to fall back to buying_power")
        if account is None or account.get("unsettled_funds") is None:
            raise ValueError("live book needs get_accounts.unsettled_funds for the agent account")
        unsettled = float(account["unsettled_funds"])
        cash = max(0.0, float(portfolio["cash"]) - unsettled)

    mapped_positions = []
    for p in positions:
        sym = (p.get("symbol") or p.get("instrument") or "").upper()
        qty = float(p.get("quantity") or p.get("qty") or 0)
        if qty <= 0 or not sym:
            continue
        avg = float(p.get("average_buy_price") or p.get("avg_cost_usd") or p.get("average_cost") or 0)
        last = float(p.get("last_price_usd") or p.get("mark_price") or p.get("last_trade_price") or avg)
        mapped_positions.append(
            {
                "symbol": sym,
                "asset_type": p.get("asset_type", "stock"),
                "sector": p.get("sector") or sector_by_symbol.get(sym, "Unknown"),
                "quantity": qty,
                "avg_cost_usd": avg,
                "entry_date": p.get("entry_date"),
                "entry_proposal_id": p.get("entry_proposal_id"),
                "conviction": p.get("conviction"),
                "stop_pct": p.get("stop_pct"),
                "stop_price_usd": p.get("stop_price_usd"),
                "take_profit_tiers_hit": list(p.get("take_profit_tiers_hit") or []),
                "last_price_usd": last,
                "last_marked_at": p.get("last_marked_at"),
            }
        )

    cash_unsettled = []
    if float(unsettled) > 0:
        cash_unsettled.append(
            {"amount_usd": float(unsettled), "settles_on": portfolio.get("unsettled_settles_on") or ""}
        )

    raw = {
        "book": book,
        "starting_capital_usd": starting_capital_usd,
        "inception_date": inception_date,
        "cash_settled_usd": float(cash),
        "cash_unsettled": cash_unsettled,
        "positions": mapped_positions,
        "closed_trades": [],
        "equity_history": [],
    }
    return normalize_ledger(raw, mode="live")


def load_book(book: str, *, mode: Optional[str] = None, live_payload: Optional[dict] = None) -> dict:
    """Load a book. Control is always paper. Live claude needs MCP payload."""
    rules = json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))
    mode = mode or rules["execution"]["mode"]

    if book == "control" or mode == "paper":
        return load_paper(book)

    if book != "claude":
        raise ValueError(f"live mode only supports claude book, got {book}")
    if live_payload is None:
        raise ValueError(
            "live claude book requires live_payload="
            "{portfolio: get_portfolio, account: get_accounts row, positions: get_equity_positions}"
        )
    if "portfolio" in live_payload and "positions" in live_payload:
        return map_live_mcp_to_ledger(
            portfolio=live_payload["portfolio"],
            positions=list(live_payload["positions"]),
            book="claude",
            starting_capital_usd=float(rules.get("account", {}).get("starting_capital_usd", 1000)),
            inception_date=live_payload.get("inception_date"),
            sector_by_symbol=live_payload.get("sector_by_symbol"),
            account=live_payload.get("account"),
        )
    # Already-normalized ledger dict
    return normalize_ledger(live_payload, mode="live")


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--book", required=True, choices=["claude", "control"])
    args = p.parse_args()
    print(json.dumps(load_book(args.book), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
