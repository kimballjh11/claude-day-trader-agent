#!/usr/bin/env python3
"""Build dashboard/data/state.json from ledgers, status, decisions, votes."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "data" / "state.json"


def _load(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _empty_book(name: str) -> dict:
    return {
        "book": name,
        "starting_capital_usd": 1000.0,
        "cash_settled_usd": 1000.0,
        "cash_unsettled": [],
        "positions": [],
        "equity_history": [],
        "closed_trades": [],
        "inception_date": None,
    }


def _equity(ledger: dict) -> float:
    unsettled = sum(u.get("amount_usd", 0) for u in ledger.get("cash_unsettled", []))
    pos = sum(
        float(p["quantity"]) * float(p.get("last_price_usd", p.get("avg_cost_usd", 0)))
        for p in ledger.get("positions", [])
    )
    return round(float(ledger.get("cash_settled_usd", 0)) + unsettled + pos, 2)


def _pct_change(hist: list[dict], days_back: int, as_of: Optional[str] = None) -> Optional[float]:
    if not hist:
        return None
    end = hist[-1]
    end_eq = float(end["equity_usd"])
    end_d = date.fromisoformat(end["date"])
    target = (end_d - timedelta(days=days_back)).isoformat()
    base = None
    for h in hist:
        if h["date"] <= target:
            base = float(h["equity_usd"])
    if base is None:
        base = float(hist[0]["equity_usd"])
    if base == 0:
        return None
    return (end_eq / base) - 1.0


def _book_tile(ledger: dict, halted: bool = False, halt_reason: Optional[str] = None) -> dict:
    start = float(ledger.get("starting_capital_usd") or 1000)
    eq = _equity(ledger)
    hist = ledger.get("equity_history") or []
    day = _pct_change(hist, 1)
    week = _pct_change(hist, 7)
    since = (eq / start - 1.0) if start else None
    unsettled = sum(u.get("amount_usd", 0) for u in ledger.get("cash_unsettled", []))
    return {
        "equity_usd": eq,
        "cash_settled_usd": float(ledger.get("cash_settled_usd", 0)),
        "cash_unsettled_usd": round(unsettled, 2),
        "day_pct": day if day is not None else 0.0,
        "week_pct": week if week is not None else 0.0,
        "since_inception_pct": since if since is not None else 0.0,
        "halted": halted,
        "halt_reason": halt_reason,
    }


def _next_take_profit(pos: dict, tiers: list[float]) -> Optional[float]:
    """Price of the lowest take-profit tier (gain_pct from risk_rules.json) not yet hit."""
    hit = {float(h) for h in (pos.get("take_profit_tiers_hit") or [])}
    avg = float(pos.get("avg_cost_usd") or 0)
    for g in sorted(tiers):
        if not any(abs(g - h) < 1e-9 for h in hit):
            return round(avg * (1 + g), 4)
    return None


def _decision_id(d: dict) -> str:
    return str(d.get("decision_id") or d.get("proposal_id") or "")


def _decision_panel(decisions: list[dict], votes: dict, *, max_rows: int = 40) -> tuple[list[dict], list[str]]:
    """Cards for the dashboard plus every votable decision id.

    Shows the last two decision dates (last evening's Phase A plus this
    morning's Phase B) and any older claude decision still unvoted, so a
    morning run never hides last evening's buys before the operator votes.
    """
    latest: dict[str, dict] = {}
    for d in decisions:
        did = _decision_id(d)
        if did:
            latest[did] = d  # later lines win (status updates)
    votable = [did for did in latest if did.endswith("-claude")]
    prefixes = sorted({did[:8] for did in latest if did[:8].isdigit()})
    recent = set(prefixes[-2:])

    cards = []
    for did, d in latest.items():
        vote = votes.get(did)
        unvoted_claude = vote is None and did.endswith("-claude")
        if did[:8] not in recent and not unvoted_claude:
            continue
        cards.append(
            {
                "decision_id": did,
                "book": d.get("book", "claude"),
                "symbol": d.get("symbol", ""),
                "action": d.get("action", ""),
                "conviction": d.get("conviction"),
                # Phase A proposals are unsized; position_sizing.py sizes them at the open.
                "amount_usd": d.get("amount_usd") or d.get("dollar_amount"),
                "status": d.get("status", "proposed"),
                "thesis_summary": d.get("thesis_summary") or "",
                "catalyst": d.get("catalyst") or "",
                "counter_case": d.get("counter_case") or "",
                "invalidation_condition": d.get("invalidation_condition") or "",
                "risk_verdict": d.get("risk_verdict") or "",
                "sources": d.get("sources") or [],
                "thesis_price": d.get("thesis_price"),
                "mom_12_1": d.get("mom_12_1"),
                "ret_60d": d.get("ret_60d"),
                "pct_from_52wk_high": d.get("pct_from_52wk_high"),
                "signals_fired": d.get("signals_fired") or [],
                "macro_regime": d.get("macro_regime") or "",
                "atd_action": d.get("atd_action") or "",
                "earnings_date": d.get("earnings_date") or "",
                "risk_flags": d.get("risk_flags") or [],
                "vote": vote,
            }
        )
    return cards[-max_rows:], votable


def _merge_equity_series(claude, control, spy) -> list[dict]:
    keys = {}
    for book_name, ledger in (("claude", claude), ("control", control), ("spy", spy)):
        for h in ledger.get("equity_history") or []:
            k = (h["date"], h.get("run", "morning"))
            keys.setdefault(k, {"date": h["date"], "run": h.get("run", "morning"),
                                "claude": None, "control": None, "spy": None})
            keys[k][book_name] = float(h["equity_usd"])
    series = []
    last = {"claude": 1000.0, "control": 1000.0, "spy": 1000.0}
    for k in sorted(keys.keys()):
        row = keys[k]
        for b in ("claude", "control", "spy"):
            if row[b] is None:
                row[b] = last[b]
            else:
                last[b] = row[b]
        series.append(row)
    if not series:
        series = [{"date": date.today().isoformat(), "run": "init",
                   "claude": 1000.0, "control": 1000.0, "spy": 1000.0}]
    return series


def _count_violations() -> int:
    """Unique rule violations logged by audit.py into state/violations.jsonl."""
    path = ROOT / "state" / "violations.jsonl"
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            n += 1
    return n


def _graduation(rules: dict, claude: dict, votes_cov: float, violations: int) -> dict:
    g = rules.get("graduation", {})
    hist = claude.get("equity_history") or []
    trading_days = len({h["date"] for h in hist})
    inception = claude.get("inception_date")
    months = 0.0
    if inception:
        d0 = date.fromisoformat(inception)
        months = (date.today() - d0).days / 30.44
    items = [
        {
            "label": f"≥ {g.get('min_trading_days', 21)} trading days",
            "met": trading_days >= int(g.get("min_trading_days", 21)),
            "detail": f"{trading_days} days",
        },
        {
            "label": f"≥ {g.get('min_calendar_months', 1)} calendar month(s)",
            "met": months >= float(g.get("min_calendar_months", 1)),
            "detail": f"{months:.1f} months",
        },
        {
            "label": "Zero rule violations",
            "met": violations <= int(g.get("max_rule_violations", 0)),
            "detail": f"{violations} violations",
        },
        {
            "label": "Clean runs (last 10 trading days)",
            "met": False,
            "detail": "tracked after scheduled runs exist",
        },
        {
            "label": "Lock tests passed (last 5 trading days)",
            "met": False,
            "detail": "see docs/ops.md",
        },
        {
            "label": f"Vote coverage ≥ {100 * float(g.get('min_vote_coverage_pct', 0.8)):.0f}%",
            "met": votes_cov >= float(g.get("min_vote_coverage_pct", 0.8)),
            "detail": f"{100 * votes_cov:.0f}%",
        },
        {
            "label": "Operator reviewed claude vs control vs SPY",
            "met": False,
            "detail": "manual",
        },
        {
            "label": "Operator set mode=live by hand",
            "met": rules.get("execution", {}).get("mode") == "live",
            "detail": f"mode={rules.get('execution', {}).get('mode')}",
        },
    ]
    return {
        "trading_days": trading_days,
        "calendar_months": round(months, 2),
        "violations": violations,
        "clean_runs_last_10": 0,
        "lock_tests_passed_at": None,
        "vote_coverage_pct": votes_cov,
        "items": items,
    }


def _scheduled_runs(schedule: dict, holidays: set[str], *, now: Optional[datetime] = None,
                    days: int = 8) -> list[dict]:
    """Every scheduled run after `now` for the next `days` days, soonest first.

    Morning/evening runs skip weekends and NYSE holidays (they stop as
    market_closed without rebuilding the dashboard); the weekly run is Friday.
    The dashboard uses this list to spot a run that never reported.
    """
    tz = ZoneInfo(schedule.get("timezone", "America/Denver"))
    now = (now or datetime.now(tz)).astimezone(tz)
    slots = [
        ("morning", schedule.get("phase_b_local_time"), False),
        ("evening", schedule.get("phase_a_local_time"), False),
        ("weekly", schedule.get("weekly_review_local_time"), True),
    ]
    out = []
    for offset in range(days + 1):
        day = now.date() + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        for run, hhmm, friday_only in slots:
            if not hhmm or (friday_only and day.weekday() != 4):
                continue
            hh, mm = map(int, hhmm.split(":"))
            at = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
            if at <= now:
                continue
            et_day = at.astimezone(ZoneInfo("America/New_York")).date().isoformat()
            if et_day in holidays and not friday_only:
                continue
            out.append({"run": run, "scheduled_at": at.isoformat()})
    out.sort(key=lambda r: r["scheduled_at"])
    return out


def build_state() -> dict:
    rules = _load(ROOT / "risk_rules.json", {})
    claude = _load(ROOT / "paper" / "claude.json", _empty_book("claude"))
    control = _load(ROOT / "paper" / "control.json", _empty_book("control"))
    bench = _load(ROOT / "paper" / "benchmark.json", {
        "starting_capital_usd": 1000,
        "equity_history": [{"date": date.today().isoformat(), "run": "init", "equity_usd": 1000}],
    })
    if "equity_history" not in bench:
        bench["equity_history"] = []
    status = _load(ROOT / "status" / "last_run.json", {
        "run": "", "started_at": "", "finished_at": "", "outcome": "ok", "errors": []
    })
    holidays_doc = _load(ROOT / "data" / "market_holidays.json", {"closed": []})
    holidays = set(holidays_doc.get("closed") or [])
    decisions = _lines(ROOT / "state" / "decisions.jsonl")
    trades = _lines(ROOT / "state" / "trade_log.jsonl")
    votes = {}
    votes_dir = ROOT / "reviews" / "votes"
    if votes_dir.exists():
        for p in votes_dir.glob("*.json"):
            try:
                v = json.loads(p.read_text(encoding="utf-8"))
                votes[v.get("decision_id") or p.stem] = v.get("vote")
            except Exception:
                pass

    decisions_today, votable_ids = _decision_panel(decisions, votes)
    unvoted = sum(1 for did in votable_ids if votes.get(did) is None)
    tp_tiers = [float(t["gain_pct"]) for t in rules.get("take_profit", {}).get("tiers", [])]

    positions = []
    sector_exposure = {"claude": [], "control": []}
    for book_name, ledger in (("claude", claude), ("control", control)):
        counts = Counter(p.get("sector", "Unknown") for p in ledger.get("positions", []))
        sector_exposure[book_name] = [{"sector": s, "count": n} for s, n in sorted(counts.items())]
        for p in ledger.get("positions", []):
            last = float(p.get("last_price_usd", p.get("avg_cost_usd", 0)))
            avg = float(p.get("avg_cost_usd", 0))
            qty = float(p["quantity"])
            positions.append(
                {
                    "book": book_name,
                    "symbol": p["symbol"],
                    "asset_type": p.get("asset_type", "stock"),
                    "sector": p.get("sector", "Unknown"),
                    "quantity": qty,
                    "avg_cost_usd": avg,
                    "last_price_usd": last,
                    "market_value_usd": round(qty * last, 2),
                    "unrealized_pct": (last / avg - 1.0) if avg else 0.0,
                    "stop_price_usd": p.get("stop_price_usd") or 0,
                    "next_take_profit_usd": _next_take_profit(p, tp_tiers) or 0,
                    "entry_date": p.get("entry_date") or "",
                    "conviction": p.get("conviction") or "",
                }
            )

    recent_trades = []
    for t in trades[-20:]:
        recent_trades.append(
            {
                "book": t.get("book", ""),
                "date": t.get("date", ""),
                "symbol": t.get("symbol", ""),
                "side": t.get("side", ""),
                "amount_usd": t.get("amount_usd") or t.get("dollar_amount") or 0,
                "price_usd": t.get("price") or t.get("price_usd") or 0,
                "reason": t.get("reason", ""),
            }
        )

    spy_eq = _equity(bench) if bench.get("positions") is not None else (
        float((bench.get("equity_history") or [{"equity_usd": 1000}])[-1]["equity_usd"])
        if bench.get("equity_history")
        else float(bench.get("indexed_equity_usd", 1000))
    )
    spy_start = float(bench.get("starting_capital_usd", 1000))

    voted_n = sum(1 for did in votable_ids if votes.get(did) is not None)
    cov = (voted_n / len(votable_ids)) if votable_ids else 0.0
    scheduled = _scheduled_runs(rules.get("schedule", {}), holidays)

    state = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": rules.get("execution", {}).get("mode", "paper"),
        "phase": rules.get("autonomy", {}).get("phase", 1),
        "last_run": {
            "run": status.get("run", ""),
            "started_at": status.get("started_at", ""),
            "finished_at": status.get("finished_at", ""),
            "outcome": status.get("outcome", "ok"),
        },
        "next_runs": scheduled[:2],
        "scheduled_runs": scheduled,
        "errors": status.get("errors") or [],
        "schedule": rules.get("schedule", {}),
        "holidays": sorted(holidays),
        "missed_run_grace_minutes": rules.get("schedule", {}).get("missed_run_grace_minutes", 60),
        "books": {
            "claude": _book_tile(claude),
            "control": _book_tile(control),
            "spy": {
                "equity_usd": spy_eq,
                "since_inception_pct": (spy_eq / spy_start - 1.0) if spy_start else 0.0,
            },
        },
        "equity_series": _merge_equity_series(claude, control, bench),
        "positions": positions,
        "sector_exposure": sector_exposure,
        "decisions_today": decisions_today,
        "votable_ids": votable_ids,
        "max_positions_per_sector": rules.get("position_sizing", {}).get("max_positions_per_sector"),
        "blocked": _load(ROOT / "state" / "blocked.json", []),
        "recent_trades": recent_trades,
        "graduation": _graduation(rules, claude, cov, _count_violations()),
        "signal_attribution": _load(ROOT / "state" / "signal_attribution.json", []),
        "unvoted_count": unvoted,
    }
    return state


def main() -> int:
    state = build_state()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(json.dumps({"ok": True, "path": str(OUT), "mode": state["mode"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
