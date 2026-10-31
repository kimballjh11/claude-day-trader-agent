# Phase B — Morning trading

_Paper Trader. Replaces FriesTrader Phase B. Spec: `TRADING_BOT_MASTER_SPEC.md` Sections 7, 9–11._

**Schedule:** weekdays 8:00am America/Denver (10:00am ET).

**Hard rules**

- Read `CLAUDE.md` first (and newest `docs/handoffs/` if present).
- Run **both books**; **claude book first**, then control.
- Never edit `risk_rules.json`, `.claude/`, or `paper/` by hand — only `python3 scripts/paper_broker.py` mutates paper ledgers.
- Never compute sizes/stops/limits in your head — run the scripts.
- In **paper** mode: **never** call `place_equity_order` or `cancel_equity_order` (denied + order guard). Simulate fills with `paper_broker.py`.
- In **live** mode (Operator-only config): place only after every gate; confirm orders; control book stays paper forever.
- Order shape (live): `type: market`, buys by `dollar_amount`, sells by `quantity`, `time_in_force: gfd`, regular hours only. Field names: `docs/mcp_tools.md` / `docs/verified.md` (VERIFY #2).
- On script failure or ledger mismatch: status error, commit, push, **stop**.

---

## B0 — Context

Read `risk_rules.json`, `CLAUDE.md`, `journal/journal.md`, `status/last_run.json`.

## B1 — Unit tests

```bash
python3 -m unittest discover tests
```

On failure → `status.py --run morning --outcome TESTS_FAILED ...`, commit, push, **stop**.

## B2 — Market open

1. If today’s date (America/New_York) is in `data/market_holidays.json` → `closed`.
2. Else check MCP market status if available.

If closed:

```bash
python3 scripts/status.py --run morning --outcome market_closed
git pull --rebase origin main && git add status/last_run.json
git commit -m "phase B: MARKET_CLOSED" && git push origin HEAD:main
```

**Stop** (not an error).

## B3 — Load books

For each book (`claude`, `control`):

```bash
python3 scripts/paper_broker.py settle --book <book> --date YYYY-MM-DD
python3 scripts/book.py --book <book>
```

Then mark both books with **fresh** `get_equity_quotes` for every held symbol, before any sell or buy. B4's daily halt compares this mark with yesterday's; without it the daily drawdown is always 0.

```bash
# data/raw/prices_open.json = {"SYMBOL": <current price>, ...} for all held symbols in both books
python3 scripts/paper_broker.py mark --book claude --prices data/raw/prices_open.json --date YYYY-MM-DD --run open
python3 scripts/paper_broker.py mark --book control --prices data/raw/prices_open.json --date YYYY-MM-DD --run open
```

Live claude book (M10+ only): load via MCP `get_portfolio` / `get_equity_positions` into the same schema. Control remains paper always.

## B4 — Loss halts

Per book, use equity history (not Robinhood realized P&L in paper):

```bash
python3 scripts/pnl_pct.py \
  --equity-history paper/<book>.json --as-of YYYY-MM-DD \
  --net-deposits-usd 1000 \
  --daily-limit-pct 0.04 --weekly-limit-pct 0.08
```

Read limits from `risk_rules.json` `loss_limits.*`. If `entries_halted` → **block buys** for that book; sells still run. Record halt for the recap and dashboard.

## B5 — Sells first

For each book, in order:

1. **Stop-loss** — `scripts/stop_loss.py` (volatility-scaled per `risk_rules.json`). Sell all if bid ≤ stop.
2. **Take-profit** — `scripts/take_profit.py` (25% at +15/+30/+50; each tier once).
3. **Conviction trim** — `scripts/conviction_trim.py` if enabled.
4. **Thesis exits** — **claude book only**. Within `early_exit_guard.window_trading_days` of entry, require a new fact dated after the entry thesis.

Queue sell orders (do not fill yet until B10; in live mode preview them in B9 first — keep sells before buys).

## B6 — Refresh buy proposals

1. Load `state/pending_proposals.jsonl` (claude) and `state/control_proposals.jsonl`.
2. Drop proposals older than **1 trading day**.
3. Fresh `get_equity_quotes` for each remaining buy/add symbol.

## B7 — Entry gates

Run `scripts/entry_gate.py` (and related checks) for each buy/add:

- Gap vs thesis price ≤ `entry_price_gap.max_pct` (3%)
- Extension ≤ 10% above 20-day MA if enabled
- Earnings blackout (stocks only; ETFs exempt per config)
- Wash sale (this agent account only)
- Re-entry lock

Blocked names go to the recap / `blocked` list — do not size them.

## B8 — Rank, size, sector, session caps

For each book’s surviving buy/add list:

Scratch JSON for this session goes under **`data/raw/`** (gitignored). Never write `candidates.json` / `ranked.json` / `prices.json` / `session_fills.json` at the repo root.

```bash
mkdir -p data/raw
# rank (stdin/stdout)
python3 scripts/rank_candidates.py < data/raw/candidates.json > data/raw/ranked.json

# size — pass conviction tiers and caps from risk_rules.json (never hard-code)
python3 scripts/position_sizing.py \
  --total-value ... --cash-start ... --concurrent-positions-start ... \
  --max-position-pct 0.15 --max-concurrent-positions 5 --min-cash-buffer-pct 0.15 \
  --min-top-up-usd 5 --min-top-up-pct-of-target 0.10 \
  --conviction-pct "high:0.15,medium:0.10,low:0.05" \
  --max-order-usd 500 --max-new-per-session 2 --max-per-sector 3 \
  --sector-counts-start "..." --min-order-usd 5 \
  < data/raw/ranked.json
```

Read numbers from `risk_rules.json` at runtime — the example flags above must match the file.

## B9 — Preview every order (live mode only)

- **Paper:** **skip this step.** Do not call `review_equity_order`. Paper fills use the fresh `get_equity_quotes` ask/bid from B6 (the operator's decision 2026-10-21: the agent account number is not set and the account holds $0).
- **Live:** for every sell and buy that passed sizing, call `review_equity_order` with the payload from `python3 scripts/live_orders.py build-buy|build-sell ... --for-review`. Any blocking alert → reject that order (`ORDER_REJECTED_PREVIEW`).

## B10 — Fill or place

### Paper (both books)

```bash
# buys at ask, sells at bid
python3 scripts/paper_broker.py fill --book <book> --side buy --symbol S \
  --dollar-amount X --price <ask> --date YYYY-MM-DD --sector ... --conviction ...
python3 scripts/paper_broker.py fill --book <book> --side sell --symbol S \
  --quantity Q --price <bid> --date YYYY-MM-DD --reason <stop_loss|take_profit|trim|thesis_exit> \
  [--take-profit-tier 0.15]   # when reason is take_profit; records tier on position
```

Partial sells are logged in `closed_trades` with `"partial": true`. Pass `--take-profit-tier` so the dashboard Next-TP column advances.

### Live (claude book only; mode must be live and permissions opened by the operator)

Requires env `RH_AGENT_ACCOUNT_NUMBER` (or the name in `risk_rules.json` `account.account_number_env_var`). `live_orders.py` embeds `account_number`, `market_hours: regular_hours`, and a fresh `ref_id` on every payload.

1. Build payload with `scripts/live_orders.py` (`build-buy` / `build-sell`). It **exits non-zero in paper mode** — do not hand-craft place args to bypass it.
2. `place_equity_order` with that payload (market / gfd / dollar_amount or quantity).
3. From the place response, record **`order_id`** (or `id`) into `data/raw/session_fills.json` and the matching `state/trade_log.jsonl` line. Without it, audit flags `LIVE_ORDER_NO_ID`.
4. Confirm with `get_equity_orders` twice (~15s apart). Classify with `live_orders.confirm_after_polls` / `classify_order_status`.
5. If held for app approval → log `pending_robinhood_approval`, status `ROBINHOOD_APPROVAL_REQUIRED`.
6. If unconfirmed → `ORDER_NOT_CONFIRMED`.
7. Load claude book via `book.load_book("claude", mode="live", live_payload={...})` where `live_payload` includes:
   - `portfolio` — `get_portfolio` response
   - `positions` — `get_equity_positions` list
   - `account` — the **agent** row from `get_accounts` (needed for `unsettled_funds`; settled cash = portfolio cash − unsettled)
   - optional `sector_by_symbol`, `inception_date`

Control book: always paper fills, even when claude is live.

## B11 — Logs, recap, audit, dashboard

1. Append every stage to `state/trade_log.jsonl` (include `book`, `mode`; live fills must include `order_id`).
2. Mark books and SPY:

```bash
python3 scripts/paper_broker.py mark --book claude --prices data/raw/prices.json --date D --run morning
python3 scripts/paper_broker.py mark --book control --prices data/raw/prices.json --date D --run morning
# SPY benchmark (indexed to $1000). First run ever: also pass --inception-spy <price that day>
python3 scripts/paper_broker.py benchmark --spy-price <SPY> --date D --run morning [--inception-spy <SPY>]
# Merge today's closes into price history for weekly attribution (gitignored)
# data/raw/price_history.json shape: {"YYYY-MM-DD": {"AAPL": 1.23, "SPY": 4.56, ...}}
```

3. Write `recaps/YYYY-MM-DD.md`:
   - Per book: buys/sells and why; blocked trades + rule; halts; ending equity vs start vs SPY; ignored instructions; errors.
4. Append votable **sell** decisions (claude) to `state/decisions.jsonl`.
5. Run:

```bash
python3 scripts/audit.py --fills data/raw/session_fills.json --ledgers paper/claude.json paper/control.json
python3 scripts/build_dashboard_data.py
python3 scripts/status.py --run morning --outcome ok   # or warning/error
```

If audit finds violations → outcome `error`, code `RULE_VIOLATION`, **do not hide it**.

## B12 — Commit

```bash
git pull --rebase origin main
git add -A
git commit -m "phase B YYYY-MM-DD: <summary>"
git push origin HEAD:main
```
