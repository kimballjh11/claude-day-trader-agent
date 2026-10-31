#!/usr/bin/env python3
# Part of FriesTrader (https://github.com/YizhiSong/FriesTrader)
# Copyright (c) 2026 Yizhi Song, MIT License -- see LICENSE
# Modified for Claude Day Trader Agent: mom_12_1 descending, then fewer risk_flags (Section 7.5).
"""Sort buy/add candidates: conviction, then mom_12_1 desc, then fewer risk_flags."""
import json
import sys

CONVICTION_RANK = {"high": 0, "medium": 1, "low": 2}
MISSING_RISK_FLAGS_SENTINEL = 10 ** 9
MISSING_MOM_SENTINEL = float("-inf")


def sort_key(candidate):
    conviction_rank = CONVICTION_RANK[candidate["conviction"]]
    mom = candidate.get("mom_12_1")
    mom_key = mom if mom is not None else MISSING_MOM_SENTINEL
    if "risk_flags" in candidate and candidate["risk_flags"] is not None:
        risk_flags_count = len(candidate["risk_flags"])
    else:
        risk_flags_count = MISSING_RISK_FLAGS_SENTINEL
    return (
        conviction_rank,
        -mom_key if mom_key != MISSING_MOM_SENTINEL else float("inf"),
        risk_flags_count,
    )


def main():
    try:
        candidates = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid candidates JSON on stdin: {e}"}), file=sys.stderr)
        sys.exit(1)

    for c in candidates:
        if c.get("conviction") not in CONVICTION_RANK:
            print(
                json.dumps(
                    {
                        "error": f"symbol {c.get('symbol')!r} has missing/invalid "
                        f"conviction {c.get('conviction')!r}"
                    }
                ),
                file=sys.stderr,
            )
            sys.exit(1)

    candidates.sort(key=sort_key)
    print(json.dumps(candidates))


if __name__ == "__main__":
    main()
