#!/usr/bin/env python3
# Part of FriesTrader (https://github.com/YizhiSong/FriesTrader)
# Copyright (c) 2026 Yizhi Song, MIT License -- see LICENSE
# Modified for Claude Day Trader Agent: tiers from config, max_order_usd, session/sector caps (Section 7.6).
"""Size buy/add candidates in priority order. Reads JSON array from stdin."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter


def parse_pct_map(s: str) -> dict:
    out = {}
    for part in s.split(","):
        tier, pct = part.split(":")
        out[tier] = float(pct)
    return out


def parse_sector_counts(s: str) -> Counter:
    counts: Counter = Counter()
    if not s or not str(s).strip():
        return counts
    for part in str(s).split(","):
        if not part.strip():
            continue
        sector, n = part.rsplit(":", 1)
        counts[sector.strip()] = int(n)
    return counts


def size_order_amount(
    *,
    conviction_pct: float,
    total_value: float,
    max_order_usd: float,
    cash_remaining: float,
    min_cash_buffer: float,
) -> float:
    tier_amount = conviction_pct * total_value
    available = cash_remaining - min_cash_buffer
    return floor_cents(min(tier_amount, max_order_usd, max(0.0, available)))


def floor_cents(x: float) -> float:
    """Round down to the cent so an order never breaches the cash floor by rounding."""
    return math.floor(x * 100) / 100


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--total-value", type=float, required=True)
    p.add_argument("--cash-start", type=float, required=True)
    p.add_argument("--concurrent-positions-start", type=int, required=True)
    p.add_argument("--entries-halted", action="store_true")
    p.add_argument("--max-position-pct", type=float, required=True)
    p.add_argument("--max-concurrent-positions", type=int, required=True)
    p.add_argument("--min-cash-buffer-pct", type=float, required=True)
    p.add_argument("--min-top-up-usd", type=float, required=True)
    p.add_argument("--min-top-up-pct-of-target", type=float, required=True)
    p.add_argument("--conviction-pct", type=parse_pct_map, required=True)
    p.add_argument("--max-order-usd", type=float, required=True)
    p.add_argument("--max-new-per-session", type=int, required=True)
    p.add_argument("--max-per-sector", type=int, required=True)
    p.add_argument("--sector-counts-start", type=parse_sector_counts, default="")
    p.add_argument("--min-order-usd", type=float, default=5.0)
    args = p.parse_args(argv)

    try:
        candidates = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid candidates JSON on stdin: {e}"}), file=sys.stderr)
        sys.exit(1)

    cash_remaining = args.cash_start
    concurrent_positions_after = args.concurrent_positions_start
    new_this_session = 0
    sector_counts: Counter = Counter(args.sector_counts_start)
    min_cash_buffer = args.min_cash_buffer_pct * args.total_value
    results = []

    for c in candidates:
        symbol = c["symbol"]
        group = c["group"]
        conviction = c["conviction"]
        sector = c.get("sector", "Unknown")
        conviction_pct = args.conviction_pct[conviction]

        if args.entries_halted:
            halted = {
                "symbol": symbol,
                "group": group,
                "conviction": conviction,
                "sector": sector,
                "passed": False,
                "reason": "loss limit halt — daily/weekly drawdown breached",
            }
            if group == "held":
                halted["position_action"] = "top_up"
            results.append(halted)
            continue

        if group == "new":
            reasons = []
            if new_this_session >= args.max_new_per_session:
                reasons.append(
                    f"max_new_positions_per_session ({args.max_new_per_session}) already filled"
                )
            if concurrent_positions_after + 1 > args.max_concurrent_positions:
                reasons.append(
                    f"concurrent_positions_after would exceed "
                    f"max_concurrent_positions ({args.max_concurrent_positions})"
                )
            if sector_counts[sector] + 1 > args.max_per_sector:
                reasons.append(
                    f"sector {sector} at {sector_counts[sector]} "
                    f"(max_positions_per_sector {args.max_per_sector})"
                )
            if conviction_pct > args.max_position_pct:
                reasons.append(
                    f"conviction tier {conviction_pct:.4%} exceeds "
                    f"max_position_pct_of_account {args.max_position_pct:.4%}"
                )

            dollar_amount = size_order_amount(
                conviction_pct=conviction_pct,
                total_value=args.total_value,
                max_order_usd=args.max_order_usd,
                cash_remaining=cash_remaining,
                min_cash_buffer=min_cash_buffer,
            )
            if dollar_amount < args.min_order_usd:
                reasons.append(
                    f"order ${dollar_amount:.2f} below min_order_usd ${args.min_order_usd:.2f}"
                )

            candidate_cash_after = cash_remaining - dollar_amount
            if candidate_cash_after < min_cash_buffer:
                reasons.append(
                    f"cash_remaining after trade (${candidate_cash_after:.2f}) would fall below "
                    f"min_cash_buffer_pct (${min_cash_buffer:.2f})"
                )

            if reasons:
                results.append(
                    {
                        "symbol": symbol,
                        "group": group,
                        "conviction": conviction,
                        "sector": sector,
                        "passed": False,
                        "reason": "; ".join(reasons),
                        "dollar_amount": dollar_amount,
                    }
                )
                continue

            cash_remaining = candidate_cash_after
            concurrent_positions_after += 1
            new_this_session += 1
            sector_counts[sector] += 1
            results.append(
                {
                    "symbol": symbol,
                    "group": group,
                    "conviction": conviction,
                    "sector": sector,
                    "passed": True,
                    "dollar_amount": dollar_amount,
                    "concurrent_positions_after": concurrent_positions_after,
                    "new_positions_this_session": new_this_session,
                    "cash_remaining_after": round(cash_remaining, 2),
                    "cash_buffer_after_pct": round(cash_remaining / args.total_value, 6),
                }
            )

        elif group == "held":
            current_position_value = c["current_position_value"]
            target_size = conviction_pct * args.total_value
            headroom = target_size - current_position_value

            if headroom <= 0:
                results.append(
                    {
                        "symbol": symbol,
                        "group": group,
                        "conviction": conviction,
                        "sector": sector,
                        "passed": False,
                        "position_action": "top_up",
                        "reason": "already at or above target size for its conviction tier — no top-up",
                        "current_position_value": round(current_position_value, 2),
                        "target_size": round(target_size, 2),
                        "headroom": round(headroom, 2),
                    }
                )
                continue

            ceiling_room = args.max_position_pct * args.total_value - current_position_value
            top_up_amount = floor_cents(
                min(
                    headroom,
                    ceiling_room,
                    args.max_order_usd,
                    max(0.0, cash_remaining - min_cash_buffer),
                )
            )
            min_top_up_threshold = round(
                max(1.00, args.min_top_up_usd, args.min_top_up_pct_of_target * target_size),
                2,
            )

            if top_up_amount < min_top_up_threshold:
                results.append(
                    {
                        "symbol": symbol,
                        "group": group,
                        "conviction": conviction,
                        "sector": sector,
                        "passed": False,
                        "position_action": "top_up",
                        "reason": (
                            f"top-up amount ${top_up_amount:.2f} is below the min top-up threshold "
                            f"${min_top_up_threshold:.2f}"
                        ),
                        "current_position_value": round(current_position_value, 2),
                        "target_size": round(target_size, 2),
                        "headroom": round(headroom, 2),
                    }
                )
                continue

            if top_up_amount < args.min_order_usd:
                results.append(
                    {
                        "symbol": symbol,
                        "group": group,
                        "conviction": conviction,
                        "sector": sector,
                        "passed": False,
                        "position_action": "top_up",
                        "reason": (
                            f"top-up ${top_up_amount:.2f} below min_order_usd ${args.min_order_usd:.2f}"
                        ),
                        "current_position_value": round(current_position_value, 2),
                        "target_size": round(target_size, 2),
                        "headroom": round(headroom, 2),
                    }
                )
                continue

            candidate_cash_after = cash_remaining - top_up_amount
            if candidate_cash_after < min_cash_buffer:
                results.append(
                    {
                        "symbol": symbol,
                        "group": group,
                        "conviction": conviction,
                        "sector": sector,
                        "passed": False,
                        "position_action": "top_up",
                        "reason": (
                            f"cash_remaining after trade (${candidate_cash_after:.2f}) would fall below "
                            f"min_cash_buffer_pct (${min_cash_buffer:.2f})"
                        ),
                        "current_position_value": round(current_position_value, 2),
                        "target_size": round(target_size, 2),
                        "headroom": round(headroom, 2),
                    }
                )
                continue

            cash_remaining = candidate_cash_after
            results.append(
                {
                    "symbol": symbol,
                    "group": group,
                    "conviction": conviction,
                    "sector": sector,
                    "passed": True,
                    "position_action": "top_up",
                    "current_position_value": round(current_position_value, 2),
                    "target_size": round(target_size, 2),
                    "headroom": round(headroom, 2),
                    "dollar_amount": top_up_amount,
                    "cash_remaining_after": round(cash_remaining, 2),
                    "cash_buffer_after_pct": round(cash_remaining / args.total_value, 6),
                }
            )
        else:
            print(
                json.dumps({"error": f"unknown group '{group}' for symbol {symbol}"}),
                file=sys.stderr,
            )
            sys.exit(1)

    print(
        json.dumps(
            {
                "results": results,
                "cash_remaining_final": round(cash_remaining, 2),
                "concurrent_positions_after_final": concurrent_positions_after,
                "new_positions_this_session_final": new_this_session,
                "sector_counts_final": dict(sector_counts),
            }
        )
    )


if __name__ == "__main__":
    main()
