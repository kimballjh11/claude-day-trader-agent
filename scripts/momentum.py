#!/usr/bin/env python3
"""Momentum metrics and signal gate per master spec Section 7.3."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def _closes(bars: Sequence[Mapping[str, Any]]) -> list[float]:
    return [float(b["close"]) for b in bars]


def sma(values: Sequence[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    chunk = values[-window:]
    return sum(chunk) / window


def ret_60d(bars: Sequence[Mapping[str, Any]], *, as_of: Optional[date] = None) -> Optional[float]:
    if not bars:
        return None
    today = as_of or _parse_date(bars[-1]["date"])
    target = today - timedelta(days=60)
    close_today = float(bars[-1]["close"])
    prior = None
    for b in bars:
        d = _parse_date(b["date"])
        if d <= target:
            prior = float(b["close"])
        else:
            break
    if prior is None or prior == 0:
        return None
    return close_today / prior - 1.0


def mom_12_1(bars: Sequence[Mapping[str, Any]]) -> Optional[float]:
    if len(bars) < 253:
        return None
    c_skip = float(bars[-(1 + 21)]["close"])
    c_old = float(bars[-(1 + 252)]["close"])
    if c_old == 0:
        return None
    return c_skip / c_old - 1.0


def vol_ratio(bars: Sequence[Mapping[str, Any]]) -> Optional[float]:
    if len(bars) < 31 or "volume" not in bars[-1]:
        return None
    today_vol = float(bars[-1]["volume"])
    prior = [float(b["volume"]) for b in bars[-31:-1]]
    mean_vol = sum(prior) / len(prior)
    if mean_vol == 0:
        return None
    return today_vol / mean_vol


def high_52wk(bars: Sequence[Mapping[str, Any]]) -> Optional[float]:
    window = bars[-252:] if len(bars) >= 252 else bars
    if not window:
        return None
    highs = []
    for b in window:
        if "high" in b and b["high"] is not None:
            highs.append(float(b["high"]))
        else:
            highs.append(float(b["close"]))
    return max(highs) if highs else None


def pct_from_52wk_high(bars: Sequence[Mapping[str, Any]]) -> Optional[float]:
    h = high_52wk(bars)
    if h is None or h == 0:
        return None
    close = float(bars[-1]["close"])
    return (h - close) / h


def sma_200(bars: Sequence[Mapping[str, Any]]) -> Optional[float]:
    return sma(_closes(bars), 200)


def compute_metrics(bars: Sequence[Mapping[str, Any]]) -> dict:
    m12 = mom_12_1(bars)
    return {
        "ret_60d": ret_60d(bars),
        "mom_12_1": m12,
        "vol_ratio": vol_ratio(bars),
        "pct_from_52wk_high": pct_from_52wk_high(bars),
        "sma_200": sma_200(bars),
        "bar_count": len(bars),
        "mom_12_1_null_insufficient_bars": m12 is None and len(bars) < 253,
    }


def signal_gate(
    metrics: Mapping[str, Any],
    bars: Sequence[Mapping[str, Any]],
    rules: Mapping[str, Any],
    *,
    is_holding: bool = False,
) -> dict:
    gate = rules.get("signal_gate", {})
    if is_holding:
        return {"passed": True, "signals_fired": ["holding_exempt"], "reason": None}

    mom = metrics.get("mom_12_1")
    if gate.get("momentum_12_1_must_be_positive", True):
        if mom is None:
            return {"passed": False, "signals_fired": [], "reason": "mom_12_1_null"}
        if not (mom > 0):
            return {"passed": False, "signals_fired": [], "reason": "mom_12_1_not_positive"}

    fired: list[str] = []
    ret = metrics.get("ret_60d")
    if ret is not None and ret >= gate.get("price_move_60d_min_pct", 0.10):
        fired.append("ret_60d")

    vr = metrics.get("vol_ratio")
    if vr is not None and vr >= gate.get("volume_spike_multiple", 2.0):
        up_ok = True
        if gate.get("volume_spike_requires_up_day", True):
            if len(bars) < 2:
                up_ok = False
            else:
                up_ok = float(bars[-1]["close"]) > float(bars[-2]["close"])
        if up_ok:
            fired.append("vol_ratio")

    pct = metrics.get("pct_from_52wk_high")
    if pct is not None and pct <= gate.get("near_52wk_high_pct", 0.03):
        fired.append("near_52wk_high")

    if not fired:
        return {"passed": False, "signals_fired": [], "reason": "no_trigger"}
    return {"passed": True, "signals_fired": fired, "reason": None}


def research_shortlist(
    candidates: Sequence[Mapping[str, Any]],
    *,
    max_research: int,
) -> list[dict]:
    holdings = [dict(c) for c in candidates if c.get("is_holding")]
    non_held = [
        dict(c) for c in candidates if not c.get("is_holding") and c.get("gate_passed")
    ]
    non_held.sort(
        key=lambda c: (
            c.get("mom_12_1") is None,
            -(c.get("mom_12_1") if c.get("mom_12_1") is not None else 0.0),
        )
    )
    picked = non_held[:max_research]
    seen = {c["symbol"] for c in holdings}
    out = list(holdings)
    for c in picked:
        if c["symbol"] not in seen:
            out.append(c)
            seen.add(c["symbol"])
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rules", default="risk_rules.json")
    p.add_argument("--bars", required=True)
    p.add_argument("--holdings", default="")
    args = p.parse_args(argv)

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    bars_by_sym = json.loads(Path(args.bars).read_text(encoding="utf-8"))
    holdings = {s.strip().upper() for s in args.holdings.split(",") if s.strip()}

    results = []
    for symbol, bars in bars_by_sym.items():
        metrics = compute_metrics(bars)
        gate = signal_gate(metrics, bars, rules, is_holding=symbol.upper() in holdings)
        results.append(
            {
                "symbol": symbol.upper(),
                "is_holding": symbol.upper() in holdings,
                **metrics,
                "gate_passed": gate["passed"],
                "signals_fired": gate["signals_fired"],
                "gate_reason": gate["reason"],
            }
        )
    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
