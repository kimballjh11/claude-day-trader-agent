#!/usr/bin/env python3
# Part of FriesTrader (https://github.com/YizhiSong/FriesTrader)
# Copyright (c) 2026 Yizhi Song, MIT License -- see LICENSE
"""Compute daily/weekly P&L % against the loss-limit base and the halt decision.

Paper mode: pass --equity-history (ledger equity_history JSON) so drawdowns include
open-position MTM, not only realized closes from Robinhood get_realized_pnl.

Live mode: may still pass --daily-realized-usd / --weekly-realized-usd from MCP;
prefer equity-history when available.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional


def _equity_on_or_before(history: list[dict], d: str) -> Optional[float]:
    hits = [h for h in history if h.get("date") and h["date"] <= d]
    if not hits:
        return None
    return float(hits[-1]["equity_usd"])


def _week_start_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def drawdown_from_history(
    history: list[dict],
    *,
    as_of: str,
    net_deposits_usd: float,
) -> dict:
    """Daily = latest mark on/before as_of vs the last mark on an EARLIER date;
    weekly = latest mark vs the last mark before this week's Monday.

    Phase B marks the books with fresh quotes (B3) before calling this, so the
    latest mark is this morning and the bases are yesterday / last Friday.
    """
    if net_deposits_usd <= 0:
        raise ValueError("net_deposits_usd must be positive")
    if not history:
        return {
            "daily_pnl_pct": 0.0,
            "weekly_pnl_pct": 0.0,
            "daily_pnl_usd": 0.0,
            "weekly_pnl_usd": 0.0,
        }
    as_of_d = date.fromisoformat(as_of)
    end = _equity_on_or_before(history, as_of)
    if end is None:
        end = float(history[-1]["equity_usd"])

    prev_day = (as_of_d - timedelta(days=1)).isoformat()
    day_base = _equity_on_or_before(history, prev_day)
    if day_base is None:
        day_base = end

    # Last mark before Monday (normally Friday's), so Monday's move counts.
    before_week = (_week_start_monday(as_of_d) - timedelta(days=1)).isoformat()
    week_base = _equity_on_or_before(history, before_week)
    if week_base is None:
        week_base = end

    daily_usd = end - day_base
    weekly_usd = end - week_base
    return {
        "daily_pnl_usd": round(daily_usd, 2),
        "weekly_pnl_usd": round(weekly_usd, 2),
        "daily_pnl_pct": daily_usd / net_deposits_usd,
        "weekly_pnl_pct": weekly_usd / net_deposits_usd,
        "equity_usd": end,
        "day_base_usd": day_base,
        "week_base_usd": week_base,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--daily-realized-usd", type=float, default=None,
                    help="legacy: get_realized_pnl span=day (ignored if --equity-history set)")
    p.add_argument("--weekly-realized-usd", type=float, default=None,
                    help="legacy: get_realized_pnl span=week (ignored if --equity-history set)")
    p.add_argument("--net-deposits-usd", type=float, required=True,
                    help="starting capital / net deposits (paper: usually 1000)")
    p.add_argument("--daily-limit-pct", type=float, required=True)
    p.add_argument("--weekly-limit-pct", type=float, required=True)
    p.add_argument("--equity-history", default="",
                    help="path to JSON list of {date, equity_usd} or a paper ledger file")
    p.add_argument("--as-of", default="", help="YYYY-MM-DD (required with --equity-history)")
    args = p.parse_args()

    if args.net_deposits_usd <= 0:
        print(json.dumps({"error": "net_deposits_usd must be positive"}), file=sys.stderr)
        sys.exit(1)

    if args.equity_history:
        if not args.as_of:
            print(json.dumps({"error": "--as-of required with --equity-history"}), file=sys.stderr)
            sys.exit(1)
        raw = json.loads(Path(args.equity_history).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            history = raw.get("equity_history") or []
            if args.net_deposits_usd <= 0:
                args.net_deposits_usd = float(raw.get("starting_capital_usd") or 1000)
        else:
            history = raw
        stats = drawdown_from_history(
            history, as_of=args.as_of, net_deposits_usd=args.net_deposits_usd
        )
        daily_pnl_pct = stats["daily_pnl_pct"]
        weekly_pnl_pct = stats["weekly_pnl_pct"]
        extra = {k: stats[k] for k in ("daily_pnl_usd", "weekly_pnl_usd", "equity_usd",
                                       "day_base_usd", "week_base_usd")}
    else:
        if args.daily_realized_usd is None or args.weekly_realized_usd is None:
            print(json.dumps({"error": "pass --equity-history or both realized-usd flags"}),
                  file=sys.stderr)
            sys.exit(1)
        daily_pnl_pct = args.daily_realized_usd / args.net_deposits_usd
        weekly_pnl_pct = args.weekly_realized_usd / args.net_deposits_usd
        extra = {}

    daily_breach = (-daily_pnl_pct) >= args.daily_limit_pct
    weekly_breach = (-weekly_pnl_pct) >= args.weekly_limit_pct

    reasons = []
    if daily_breach:
        reasons.append(
            f"daily drawdown {(-daily_pnl_pct):.4%} >= daily limit {args.daily_limit_pct:.4%}"
        )
    if weekly_breach:
        reasons.append(
            f"weekly drawdown {(-weekly_pnl_pct):.4%} >= weekly limit {args.weekly_limit_pct:.4%}"
        )

    out = {
        "daily_pnl_pct": round(daily_pnl_pct, 6),
        "weekly_pnl_pct": round(weekly_pnl_pct, 6),
        "entries_halted": daily_breach or weekly_breach,
        "halt_reason": "; ".join(reasons) if reasons else None,
        **extra,
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
