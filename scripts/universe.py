#!/usr/bin/env python3
"""Universe eligibility filters per TRADING_BOT_MASTER_SPEC.md Section 7.1."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

ETN_KEYWORDS = ("etn", "exchange traded note", "exchange-traded note")
CRYPTO_KEYWORDS = (
    "bitcoin",
    " ethereum",
    "ether ",
    "crypto",
    " cryptocurrency",
    "solana",
    "xrp ",
    " dogecoin",
)
OPTION_INCOME_KEYWORDS = (
    "yieldmax",
    "weeklypay",
    " covered call",
    "buywrite",
    " buy-write",
    "option income",
    "0dte",
    " 0dte",
)
COMMODITY_KEYWORDS = (
    " crude oil",
    " wti ",
    " brent ",
    " natural gas",
    " gold futures",
    " silver futures",
    " commodity",
    " oil fund",
)


def load_risk_rules(path: Path | str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_symbol_set(csv_path: Path | str, symbol_column: str = "symbol") -> set[str]:
    path = Path(csv_path)
    if not path.exists():
        return set()
    out: set[str] = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get(symbol_column) or "").strip().upper()
            if sym:
                out.add(sym)
    return out


def load_sp500_sectors(csv_path: Path | str) -> dict[str, str]:
    path = Path(csv_path)
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip().upper()
            sector = (row.get("sector") or "").strip() or "Unknown"
            if sym:
                out[sym] = sector
    return out


def _name_blob(name: Optional[str], symbol: str) -> str:
    return f" {(name or '')} {symbol} ".lower()


def is_excluded_product(
    symbol: str,
    *,
    name: Optional[str] = None,
    asset_type: str = "stock",
    etf_exclusions: Optional[Iterable[str]] = None,
    instrument_leverage: Optional[float] = None,
    instrument_type: Optional[str] = None,
    rules: Optional[Mapping[str, Any]] = None,
) -> tuple[bool, Optional[str]]:
    rules = rules or {}
    uni = rules.get("universe", {})
    sym = symbol.strip().upper()
    exclusions = {s.strip().upper() for s in (etf_exclusions or [])}

    if sym in exclusions:
        return True, "listed_in_etf_exclusions"

    itype = (instrument_type or "").lower()
    if uni.get("exclude_etns", True) and (
        "etn" in itype or any(k in _name_blob(name, sym) for k in ETN_KEYWORDS)
    ):
        return True, "etn"

    if instrument_leverage is not None:
        if uni.get("exclude_leveraged_etfs", True) and abs(instrument_leverage) >= 1.5:
            return True, f"leverage_field={instrument_leverage}"
        if uni.get("exclude_inverse_etfs", True) and instrument_leverage < 0:
            return True, f"inverse_leverage_field={instrument_leverage}"

    blob = _name_blob(name, sym)
    if asset_type.lower() == "etf" or "etf" in itype or "etf" in blob:
        if uni.get("exclude_volatility_products", True) and (
            "vix" in blob or "volatility" in blob
        ):
            return True, "volatility_product_keyword"
        if uni.get("exclude_inverse_etfs", True) and any(
            k in blob for k in ("inverse", " short ", "bear", "-1x")
        ):
            return True, "inverse_keyword"
        if uni.get("exclude_leveraged_etfs", True) and any(
            k in blob for k in ("2x", "3x", "ultra", "-1x")
        ):
            return True, "leveraged_keyword"
        if uni.get("exclude_leveraged_etfs", True) and re.search(
            r"\bdaily\b.*\b(bull|bear|long|short|2x|3x)\b|\b(bull|bear)\b.*\bdaily\b",
            blob,
        ):
            return True, "leveraged_daily_keyword"
        if uni.get("exclude_crypto_products", True) and any(k in blob for k in CRYPTO_KEYWORDS):
            return True, "crypto_product_keyword"
        if uni.get("exclude_option_income_etfs", True) and any(
            k in blob for k in OPTION_INCOME_KEYWORDS
        ):
            return True, "option_income_etf_keyword"
        if uni.get("exclude_commodity_etfs", True) and any(k in blob for k in COMMODITY_KEYWORDS):
            return True, "commodity_etf_keyword"

    return False, None


def passes_membership(
    symbol: str,
    *,
    asset_type: str,
    market_cap_usd: Optional[float],
    sp500: Mapping[str, Any] | set[str],
    rules: Mapping[str, Any],
) -> tuple[bool, Optional[str]]:
    uni = rules["universe"]
    sym = symbol.strip().upper()
    at = asset_type.lower()

    if at == "etf":
        if not uni.get("allow_etfs", True):
            return False, "etfs_not_allowed"
        return True, None

    if uni.get("include_sp500_any_size", True) and sym in sp500:
        return True, None

    if market_cap_usd is None:
        return False, "missing_market_cap_and_not_sp500"

    lo = uni["other_us_stocks_min_market_cap_usd"]
    hi = uni["other_us_stocks_max_market_cap_usd"]
    if lo <= market_cap_usd <= hi:
        return True, None
    if market_cap_usd < lo:
        return False, f"market_cap_below_{lo}"
    return False, f"market_cap_above_{hi}"


def passes_liquidity_and_price(
    *,
    price: Optional[float],
    avg_daily_volume: Optional[float],
    rules: Mapping[str, Any],
) -> tuple[bool, Optional[str]]:
    uni = rules["universe"]
    if price is None or price < uni["min_price_usd"]:
        return False, "price_below_min"
    if avg_daily_volume is None or avg_daily_volume < uni["min_avg_daily_volume"]:
        return False, "volume_below_min"
    return True, None


def passes_trend_filter(
    *,
    close: Optional[float],
    sma_200: Optional[float],
    is_holding: bool,
    rules: Mapping[str, Any],
) -> tuple[bool, Optional[str]]:
    uni = rules["universe"]
    if not uni.get("trend_filter_enabled", True):
        return True, None
    if is_holding and not uni.get("trend_filter_applies_to_holdings", False):
        return True, None
    if close is None or sma_200 is None:
        return False, "missing_sma_or_close"
    if close > sma_200:
        return True, None
    return False, "below_sma_200"


def evaluate_symbol(
    *,
    symbol: str,
    asset_type: str,
    rules: Mapping[str, Any],
    sp500: Mapping[str, Any] | set[str],
    etf_exclusions: Iterable[str],
    price: Optional[float] = None,
    avg_daily_volume: Optional[float] = None,
    market_cap_usd: Optional[float] = None,
    close: Optional[float] = None,
    sma_200: Optional[float] = None,
    is_holding: bool = False,
    name: Optional[str] = None,
    instrument_leverage: Optional[float] = None,
    instrument_type: Optional[str] = None,
    apply_trend: bool = True,
) -> dict:
    reasons: list[str] = []

    excluded, ex_reason = is_excluded_product(
        symbol,
        name=name,
        asset_type=asset_type,
        etf_exclusions=etf_exclusions,
        instrument_leverage=instrument_leverage,
        instrument_type=instrument_type,
        rules=rules,
    )
    if excluded:
        return {"symbol": symbol.upper(), "eligible": False, "reasons": [ex_reason]}

    ok, reason = passes_membership(
        symbol,
        asset_type=asset_type,
        market_cap_usd=market_cap_usd,
        sp500=sp500,
        rules=rules,
    )
    if not ok:
        reasons.append(reason or "membership")

    ok, reason = passes_liquidity_and_price(
        price=price if price is not None else close,
        avg_daily_volume=avg_daily_volume,
        rules=rules,
    )
    if not ok:
        reasons.append(reason or "liquidity")

    if apply_trend:
        ok, reason = passes_trend_filter(
            close=close if close is not None else price,
            sma_200=sma_200,
            is_holding=is_holding,
            rules=rules,
        )
        if not ok:
            reasons.append(reason or "trend")

    return {
        "symbol": symbol.upper(),
        "eligible": len(reasons) == 0,
        "reasons": reasons,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rules", default="risk_rules.json")
    p.add_argument("--sp500", default="data/universe/sp500.csv")
    p.add_argument("--exclusions", default="data/universe/etf_exclusions.csv")
    p.add_argument("--candidates", required=True)
    args = p.parse_args(argv)

    rules = load_risk_rules(args.rules)
    sp500 = load_sp500_sectors(args.sp500)
    exclusions = load_symbol_set(args.exclusions)
    with open(args.candidates, encoding="utf-8") as f:
        candidates = json.load(f)

    results = [
        evaluate_symbol(
            symbol=c["symbol"],
            asset_type=c.get("asset_type", "stock"),
            rules=rules,
            sp500=sp500,
            etf_exclusions=exclusions,
            price=c.get("price"),
            avg_daily_volume=c.get("avg_daily_volume"),
            market_cap_usd=c.get("market_cap_usd"),
            close=c.get("close"),
            sma_200=c.get("sma_200"),
            is_holding=bool(c.get("is_holding", False)),
            name=c.get("name"),
            instrument_leverage=c.get("instrument_leverage"),
            instrument_type=c.get("instrument_type"),
            apply_trend=c.get("apply_trend", True),
        )
        for c in candidates
    ]
    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
