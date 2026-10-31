# Weekly review — Friday

_Claude Day Trader Agent. Spec: `TRADING_BOT_MASTER_SPEC.md` Section 13._

**Schedule:** Friday 4:30pm America/Denver.

**Hard rules**

- Read `CLAUDE.md` first (and newest `docs/handoffs/` if present).
- Prompts and `risk_rules.json` are **frozen during the week**. Any change is proposed here, noted in the journal, and applied only after the operator agrees (the operator edits config by hand).
- Do not place or cancel orders.
- Run tests first; stop on failure.

---

## W0 — Context

Read `CLAUDE.md`, `risk_rules.json`, `journal/journal.md`, recent `recaps/`, `reviews/YYYY-Www.md` if any, and all `reviews/votes/`.

## W1 — Unit tests

```bash
python3 -m unittest discover tests
```

On failure → status `TESTS_FAILED`, commit, push, stop.

## W2 — Compute review metrics

```bash
python3 scripts/weekly_review.py --as-of YYYY-MM-DD --out reviews/YYYY-Www.md
```

The script (and your summary) must cover:

1. **Returns** — week and since-inception for claude, control, and SPY (time-weighted; deposits are not gains). Paper books start at $1,000 with no deposits expected.
2. **Signal attribution** — for every buy in `trade_log.jsonl` / closed+open entries with enough forward history: 5- and 20-trading-day forward return vs SPY, grouped by each `signals_fired` value, `atd_action`, `macro_regime`, and conviction.
3. **Vote agreement** — fraction of decisions with a vote; agree vs disagree rate.
4. **Violations** — any `RULE_VIOLATION` or audit hits in the week / paper period.
5. **Operational** — missed runs, test failures, MCP errors from `status/` and recaps.

## W3 — Lessons

Append **one to three** dated lessons to `journal/journal.md`. Be specific and falsifiable. Do not rewrite old entries.

## W4 — Dashboard + status

```bash
python3 scripts/build_dashboard_data.py
python3 scripts/status.py --run weekly --outcome ok
```

## W5 — Commit

```bash
git pull --rebase origin main
git add -A
git commit -m "weekly review YYYY-Www"
git push origin HEAD:main
```
