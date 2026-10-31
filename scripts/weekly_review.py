#!/usr/bin/env python3
"""Weekly returns, signal attribution helpers, and review markdown skeleton."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _equity_on(history: list[dict], d: str) -> Optional[float]:
    hits = [h for h in history if h.get("date") <= d]
    if not hits:
        return None
    return float(hits[-1]["equity_usd"])


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return (a / b) - 1.0


def iso_week_label(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def book_returns(ledger: dict, *, week_start: str, as_of: str) -> dict:
    hist = ledger.get("equity_history") or []
    start_eq = float(ledger.get("starting_capital_usd") or 1000)
    week_base = _equity_on(hist, week_start)
    if week_base is None:
        week_base = start_eq
    end = _equity_on(hist, as_of) or start_eq
    return {
        "equity_usd": end,
        "week_pct": _pct(end, week_base),
        "since_inception_pct": _pct(end, start_eq),
        "inception_equity_ref": start_eq,
    }


def load_votes() -> dict[str, dict]:
    votes_dir = ROOT / "reviews" / "votes"
    out = {}
    if not votes_dir.exists():
        return out
    for path in votes_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            did = data.get("decision_id") or path.stem
            out[did] = data
        except Exception:
            continue
    return out


def vote_stats(decisions_path: Path, votes: dict[str, dict]) -> dict:
    decisions = []
    if decisions_path.exists():
        for line in decisions_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                decisions.append(json.loads(line))
    total = len(decisions)
    voted = 0
    agree = 0
    disagree = 0
    for d in decisions:
        did = d.get("decision_id") or d.get("proposal_id")
        if did in votes:
            voted += 1
            if votes[did].get("vote") == "agree":
                agree += 1
            elif votes[did].get("vote") == "disagree":
                disagree += 1
    return {
        "decisions": total,
        "voted": voted,
        "coverage_pct": (voted / total) if total else 0.0,
        "agree": agree,
        "disagree": disagree,
    }


def _holidays() -> set[str]:
    path = ROOT / "data" / "market_holidays.json"
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("closed") or [])


def _add_trading_days(start: date, n: int, holidays: set[str]) -> Optional[date]:
    """Advance n trading days after start (start itself not counted)."""
    if n <= 0:
        return start
    cur = start
    left = n
    for _ in range(400):
        cur += timedelta(days=1)
        if cur.weekday() >= 5 or cur.isoformat() in holidays:
            continue
        left -= 1
        if left == 0:
            return cur
    return None


def _price_on(history: dict[str, dict[str, float]], symbol: str, d: str) -> Optional[float]:
    """history: {date: {SYM: price}}. Exact date, else nearest prior trading day with that symbol."""
    if d in history and symbol in history[d]:
        return float(history[d][symbol])
    prior = sorted(k for k in history if k <= d and symbol in history[k])
    if not prior:
        return None
    return float(history[prior[-1]][symbol])


def signal_attribution(
    trade_log_path: Path,
    *,
    price_history: Optional[dict[str, dict[str, float]]] = None,
    as_of: Optional[str] = None,
    holidays: Optional[set[str]] = None,
) -> list[dict]:
    """Group buys by signal tags; fill 5d/20d forward return vs SPY when prices exist."""
    holidays = holidays if holidays is not None else _holidays()
    price_history = price_history or {}
    as_of_d = date.fromisoformat(as_of) if as_of else date.today()

    # signal -> list of fwd returns (may be empty)
    fwd5: dict[str, list[float]] = defaultdict(list)
    fwd20: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)

    if trade_log_path.exists():
        for line in trade_log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            side = (row.get("side") or row.get("action") or "").lower()
            if side not in ("buy", "add"):
                continue

            tags: list[str] = []
            for sig in row.get("signals_fired") or []:
                tags.append(str(sig))
            if not tags:
                tags.append("unknown")
            if row.get("atd_action"):
                tags.append(f"atd:{row['atd_action']}")
            if row.get("macro_regime"):
                tags.append(f"regime:{row['macro_regime']}")
            if row.get("conviction"):
                tags.append(f"conviction:{row['conviction']}")

            for t in tags:
                counts[t] += 1

            entry_d_s = row.get("date") or (row.get("timestamp") or "")[:10]
            sym = (row.get("symbol") or "").upper()
            entry_px = row.get("fill_price") or row.get("price") or row.get("quote_ask")
            if not entry_d_s or not sym or not entry_px or not price_history:
                continue
            try:
                entry_d = date.fromisoformat(entry_d_s)
                entry_px = float(entry_px)
            except ValueError:
                continue

            for horizon, bucket in ((5, fwd5), (20, fwd20)):
                target = _add_trading_days(entry_d, horizon, holidays)
                if target is None or target > as_of_d:
                    continue
                td = target.isoformat()
                px = _price_on(price_history, sym, td)
                spy0 = _price_on(price_history, "SPY", entry_d_s)
                spy1 = _price_on(price_history, "SPY", td)
                if px is None or spy0 is None or spy1 is None or entry_px <= 0 or spy0 <= 0:
                    continue
                stock_ret = (px / entry_px) - 1.0
                spy_ret = (spy1 / spy0) - 1.0
                vs = stock_ret - spy_ret
                for t in tags:
                    bucket[t].append(vs)

    all_keys = sorted(set(counts) | set(fwd5) | set(fwd20))
    out = []
    for k in all_keys:
        a = fwd5.get(k) or []
        b = fwd20.get(k) or []
        out.append(
            {
                "signal": k,
                "trades": counts.get(k, 0),
                "avg_fwd_5d_vs_spy_pct": (sum(a) / len(a)) if a else None,
                "avg_fwd_20d_vs_spy_pct": (sum(b) / len(b)) if b else None,
                "fwd_5d_n": len(a),
                "fwd_20d_n": len(b),
            }
        )
    return out


def render_markdown(payload: dict) -> str:
    lines = [
        f"# Weekly review {payload['week_label']}",
        "",
        f"As of **{payload['as_of']}**. Generated `{payload['generated_at']}`.",
        "",
        "## Returns",
        "",
        "| Book | Equity | Week % | Since inception % |",
        "|---|---:|---:|---:|",
    ]
    for name in ("claude", "control", "spy"):
        r = payload["returns"][name]

        def fmt(x):
            return "n/a" if x is None else f"{100 * x:.2f}%"

        lines.append(
            f"| {name} | ${r['equity_usd']:.2f} | {fmt(r.get('week_pct'))} | {fmt(r.get('since_inception_pct'))} |"
        )
    lines += [
        "",
        "## Votes",
        "",
        f"- Decisions: {payload['votes']['decisions']}",
        f"- Voted: {payload['votes']['voted']} ({100 * payload['votes']['coverage_pct']:.0f}% coverage)",
        f"- Agree / disagree: {payload['votes']['agree']} / {payload['votes']['disagree']}",
        "",
        "## Signal attribution",
        "",
        "| Signal | Trades | Fwd 5d vs SPY | Fwd 20d vs SPY |",
        "|---|---:|---:|---:|",
    ]
    if not payload["signal_attribution"]:
        lines.append("| — | 0 | not enough data yet | not enough data yet |")
    else:
        for row in payload["signal_attribution"]:
            a = row["avg_fwd_5d_vs_spy_pct"]
            b = row["avg_fwd_20d_vs_spy_pct"]
            lines.append(
                f"| {row['signal']} | {row['trades']} | "
                f"{'n/a' if a is None else f'{100*a:.2f}%'} | "
                f"{'n/a' if b is None else f'{100*b:.2f}%'} |"
            )
    lines += [
        "",
        "## Violations / ops",
        "",
        payload.get("ops_notes") or "_None recorded by script — fill from status/recaps._",
        "",
        "## Lessons",
        "",
        "_Append 1–3 dated lessons to `journal/journal.md` in the weekly task._",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", default="")
    p.add_argument("--week-start", default="", help="YYYY-MM-DD Monday; default = as-of - 6 days")
    p.add_argument(
        "--price-history",
        default="data/raw/price_history.json",
        help="JSON {date: {SYM: price}} including SPY for attribution",
    )
    args = p.parse_args(argv)

    as_of = args.as_of
    d = date.fromisoformat(as_of)
    week_start = args.week_start or (d - timedelta(days=6)).isoformat()
    week_label = iso_week_label(d)

    claude = _load_json(ROOT / "paper" / "claude.json") or {
        "starting_capital_usd": 1000,
        "equity_history": [],
    }
    control = _load_json(ROOT / "paper" / "control.json") or {
        "starting_capital_usd": 1000,
        "equity_history": [],
    }
    bench = _load_json(ROOT / "paper" / "benchmark.json") or {
        "starting_capital_usd": 1000,
        "equity_history": [],
    }

    returns = {
        "claude": book_returns(claude, week_start=week_start, as_of=as_of),
        "control": book_returns(control, week_start=week_start, as_of=as_of),
        "spy": book_returns(
            {
                "starting_capital_usd": bench.get("starting_capital_usd", 1000),
                "equity_history": bench.get("equity_history")
                or [{"date": as_of, "equity_usd": bench.get("indexed_equity_usd", 1000)}],
            },
            week_start=week_start,
            as_of=as_of,
        ),
    }

    votes = vote_stats(ROOT / "state" / "decisions.jsonl", load_votes())
    ph_path = Path(args.price_history)
    if not ph_path.is_absolute():
        ph_path = ROOT / ph_path
    price_history = _load_json(ph_path) or {}
    signals = signal_attribution(
        ROOT / "state" / "trade_log.jsonl",
        price_history=price_history,
        as_of=as_of,
        holidays=_holidays(),
    )

    # Persist for dashboard
    attr_path = ROOT / "state" / "signal_attribution.json"
    attr_path.parent.mkdir(parents=True, exist_ok=True)
    attr_path.write_text(json.dumps(signals, indent=2) + "\n", encoding="utf-8")

    viol_path = ROOT / "state" / "violations.jsonl"
    viol_n = 0
    if viol_path.exists():
        viol_n = sum(1 for line in viol_path.read_text(encoding="utf-8").splitlines() if line.strip())
    ops = f"_Audit violations logged: {viol_n} (see state/violations.jsonl)._"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of,
        "week_start": week_start,
        "week_label": week_label,
        "returns": returns,
        "votes": votes,
        "signal_attribution": signals,
        "ops_notes": ops,
    }

    out_path = Path(args.out) if args.out else ROOT / "reviews" / f"{week_label}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(payload), encoding="utf-8")
    meta = out_path.with_suffix(".json")
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out_path), "week_label": week_label}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
