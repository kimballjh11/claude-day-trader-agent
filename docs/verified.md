# Verified facts

Record results of every VERIFY item from the master spec (Section 17) here before building on them.

## Decisions recorded (not MCP-verified)

| Date | Topic | Decision |
|---|---|---|
| 2026-10-21 | Build before agent account | M1+ scaffold proceeds before Robinhood agent account exists. |
| 2026-10-21 | Paper cash | Paper ledgers use simulated $1,000. No Robinhood cash required during paper. Real account connected after the paper trial. |
| 2026-10-21 | Trade approvals | Operator wants **no** per-order approval. Agent Settings → Safety Controls → trade approvals must be **off** when live. Dashboard reports after the fact. Confirm in app at M0 and note below. |
| 2026-10-21 | S&P 500 source (VERIFY #14) | **Primary:** community dataset CSV `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv` (symbol + sector; no API key; the operator runs `refresh_sp500.py` locally). **Fallback:** State Street SPY holdings if that dataset lags a reconstitution. Revisit if either source breaks. |
| 2026-10-21 | Vercel | Hobby deploy via GitHub login at M7. |
| 2026-10-21 | Account type | Operator wants the agent account (••••ACCT) to be **cash only, no margin**. **Verified 2026-10-21:** `get_accounts` shows `type: cash` for both the agent account and the main account (••••MAIN). Both were margin accounts before. |
| 2026-10-21 | Working copy | Keep a private working copy for live ops; this public repo is the anonymized mirror. |
| 2026-10-21 | Cloud schedules vs local MCP | Unattended cloud needs Robinhood as a **claude.ai connector** + `agent.robinhood.com` on the Default environment allowlist. Local `/mcp` OAuth does not carry into cloud containers. |
| 2026-10-21 | Cloud routines | Three routines created paused; Operator **enabled** all three same evening. |
| 2026-10-21 | Agent funding | Do **not** fund the agent account until live (M11). Paper uses simulated $1,000 ledgers only. |
| 2026-10-21 | Paper previews | Phase B skips `review_equity_order` in paper mode (no account number set, $0 balance). Previews run in live mode only; test them in the pre-funding rehearsal. |

## Cloud MCP / scheduling

**Status 2026-10-21 evening (paper day-1 ready):**

| Item | Status |
|---|---|
| Network allow `agent.robinhood.com` | Done (Operator) |
| claude.ai connector `robinhood-trading` | Done; attached to routines only |
| Three weekday/Friday routines | **ACTIVE** — see IDs below; details in `docs/ops.md` |
| Cloud smoke test | **PASSED** 2026-10-22T01:19Z — 72 unit tests OK; `get_accounts` OK; place/cancel tools **ABSENT** (deny). One-shot routine deleted/gone from UI. |
| Cloud tool prefix | **`mcp__robinhood-trading__`**. Dual `mcp__claude_ai_robinhood-trading__*` entries in settings (harmless extras). |
| VERIFY #11 (attempt place in cloud) | **Skipped for paper** — tools absent is enough |
| Agent account funding | **Deferred until M11** — see `docs/ops.md` |

**Routine IDs** (target UTC after the operator applies winter shift — see `docs/ops.md`):

| Name | Cron UTC (winter) | Denver after Nov 1 | ID |
|---|---|---|---|
| paper-trader-phase-a | `30 22 * * 1-5` | Mon–Fri 3:30pm MST | `<redacted-routine-id>` |
| paper-trader-phase-b | `0 15 * * 1-5` | Mon–Fri 8:00am MST | `<redacted-routine-id>` |
| paper-trader-weekly | `30 23 * * 5` | Fri 4:30pm MST | `<redacted-routine-id>` |

**DST:** winter UTC applied (2026-10-21); ~1h late in MDT until Nov 1 is OK for paper.

## VERIFY checklist

| # | Item | Milestone | Status | Notes |
|---|---|---|---|---|
| 1 | Exact MCP tool names and server prefix | M1 | **verified 2026-10-21** | Prefix `mcp__robinhood-trading__`. 74 tools listed in the paste area. `place_equity_order` / `cancel_equity_order` are blocked by the deny list and don't show up as callable. |
| 2 | Payload field names for orders and previews | M1 | **blocked** | Needs one `review_equity_order` example payload after MCP auth. |
| 3 | `get_equity_historicals` max range / `interpolated` | M3 | partial | Fields: `begins_at`, `open_price`, `close_price`, `high_price`, `low_price`, `volume`, `session`. No `interpolated` key on regular daily bars; `interpolated` appears on the `get_equity_quotes` close object. Limit: 10 symbols per call; an auto-picked interval targets ~2,500 bars. Max range not tested. |
| 4 | Fundamentals sector and market cap | M3 | **verified 2026-10-21** | `get_equity_fundamentals` returns `sector`, `industry`, `market_cap` (strings), max 10 symbols. Sector names are **not** GICS (AAPL = "Electronic Technology") and don't match the scanner's sector options. Keep the S&P CSV as the sector source. |
| 5 | `create_scan` filters and sort | M3 | **done 2026-10-21** | Scans created. No built-in 3M field — custom "3M change" = vs close 63 trading days ago. IDs in `risk_rules.json`. Stocks `56d14d04-5410-490b-a04f-8e8bdbc0cd14`; ETFs `a2f1e8b0-696a-4982-a226-d623e50ef4d1`. Crypto/option-income/commodity ETFs now excluded in `universe.py` + `etf_exclusions.csv`. |
| 6 | Leveraged/inverse ETF identification | M3 | pending | |
| 7 | Settled vs unsettled cash fields | M5 | **verified 2026-10-21** | `get_accounts` → `unsettled_funds`; `get_portfolio` → `cash`, `buying_power.buying_power`, `buying_power.unleveraged_buying_power`. The agent account is `cash` (switched from `limited_margin` 2026-10-21). Still size from settled cash, never from `buying_power`. |
| 8 | `review_equity_order` with low/zero buying power | M6 | deferred | Paper skips previews. Capture the alert text during the pre-funding live rehearsal. |
| 9 | NYSE holidays 2026–2027 | M3 | **provisional** | `data/market_holidays.json` filled from typical NYSE patterns; Operator should confirm on nyse.com hours-calendars. |
| 10 | Vercel Authentication blocks unauthenticated access | M7 | pending | |
| 11 | Hooks in scheduled cloud sessions | M8 | **partial** | Cloud smoke: place/cancel tools **absent** (deny works). Lock test 4 skipped for paper (`docs/ops.md`). Hook fire unproven if a place tool ever appears. |
| 12 | Claude Pro usage covers schedule | M8 | pending | |
| 13 | Trade approvals off; held-order shape | M0 / M10 | **approvals verified off** | `get_trade_approval_setting` → `human_must_approve_trades: false` (updated 2026-10-21T23:14Z). Held-order shape not yet seen. |
| — | Lock test 1 (deny place) | M4 | **pass 2026-10-21** | Claude refused $1 buy: paper mode + `place_equity_order` on deny list. No real order. |
| 14 | S&P 500 public source | M3 | **verified locally** | `python3 scripts/refresh_sp500.py` → 503 rows into `data/universe/sp500.csv` from DataHub CSV (2026-10-21). |

## MCP paste area (Operator)

Captured by Claude Code on 2026-10-21 (~23:16 UTC, after the close) right after OAuth login. Account numbers are masked. Full request schemas: `docs/mcp_tools.md`.

### Accounts (`get_accounts`, masked)

```
••••MAIN  type=cash  individual  is_default=true   agentic_allowed=false  (main account; read-only to the agent)
••••ACCT  type=cash  individual  nickname="MCP"    agentic_allowed=true   (the agent account; the only one the agent can trade)
(Both were margin / limited_margin at first capture; the operator switched both to cash on 2026-10-21.)
```

### Tool list (server `robinhood-trading`, prefix `mcp__robinhood-trading__`)

```
Account / portfolio:  get_accounts, get_portfolio, get_equity_positions, get_equity_orders,
                      get_equity_tax_lots, get_realized_pnl, get_pnl_trade_history,
                      get_limited_margin_upgrade_info
Equity market data:   get_equity_quotes, get_equity_historicals, get_equity_fundamentals,
                      get_equity_tradability, get_equity_technical_indicators,
                      get_equity_price_book, get_equity_analyst_ratings, get_financials,
                      get_earnings_calendar, get_earnings_results, search
Indexes:              get_indexes, get_index_quotes, get_index_historicals
SEC / other data:     get_sec_filing, get_sec_filing_facts, get_sec_filing_facts_catalog,
                      get_sec_filing_index, get_politician_trades
Equity orders:        review_equity_order            (preview only, does not place)
                      place_equity_order, cancel_equity_order   (exist; blocked by the deny list)
Trade approvals:      get_trade_approval_setting, get_trade_approvals, decline_trade_approval
Scanner:              get_scanner_filter_specs, get_scanner_datapoints, get_scans, preview_scan,
                      run_scan, create_scan, update_scan_config, update_scan_filters
Watchlists:           get_watchlists, get_watchlist_items, get_popular_watchlists,
                      create_watchlist, update_watchlist, add_to_watchlist,
                      remove_from_watchlist, follow_watchlist, unfollow_watchlist
Alerts:               get_alerts, get_alert_log, create_alert, update_alert, delete_alert,
                      mark_alerts_read
Options (out of scope): get_option_chains, get_option_instruments, get_option_quotes,
                      get_option_historicals, get_option_positions, get_option_orders,
                      get_option_watchlist, add_option_to_watchlist,
                      remove_option_from_watchlist, get_option_level_upgrade_info,
                      exercise_option, cancel_option_exercise
Crypto (out of scope): get_crypto_account_onboarding_info, get_crypto_orders,
                      get_crypto_positions, get_crypto_quotes, get_currency_pairs,
                      preview_crypto_order, place_crypto_order, cancel_crypto_order
```

Not in the server's list: `place_option_order`, `cancel_option_order`, `review_option_order`. They're in the deny list but never show up as tools here.

### Example `get_equity_historicals`

Call: `symbols=["SPY"], start_time="2026-10-12T00:00:00Z", interval="day"` (bounds defaults to `regular`, adjustment_type to `split`)

```json
{"data":{"results":[{"symbol":"SPY","interval":"day","bounds":"regular","bars":[
  {"begins_at":"2026-10-12T00:00:00Z","open_price":"778.780000","close_price":"778.100000","high_price":"779.397000","low_price":"777.050000","volume":18685018,"session":"reg"},
  {"begins_at":"2026-10-13T00:00:00Z","open_price":"777.340000","close_price":"778.010000","high_price":"778.750000","low_price":"775.950000","volume":25847950,"session":"reg"},
  "... 4 more bars ...",
  {"begins_at":"2026-10-20T00:00:00Z","open_price":"765.860000","close_price":"769.050000","high_price":"772.290000","low_price":"764.250000","volume":35048373,"session":"reg"}
]}]}}
```

Notes: prices are strings and volume is an int. Bars are labeled by their UTC start time. The 2026-10-21 bar was missing even after the close; the server says the newest bar's `close_price` is not the official close (use `get_equity_quotes` for that). Gaps are left out, not filled with zeros. Up to 10 symbols per call.

### Example `get_equity_quotes`

Call: `symbols=["SPY","AAPL"]`

```json
{"data":{"results":[
  {"quote":{"symbol":"SPY","last_trade_price":"773.100000","venue_last_trade_time":"2026-10-21T19:59:59.99947065Z",
            "last_non_reg_trade_price":"770.405000","venue_last_non_reg_trade_time":"2026-10-21T23:15:56.415154185Z",
            "adjusted_previous_close":"769.050000","previous_close":"769.050000","previous_close_date":"2026-10-20",
            "bid_price":"770.380000","venue_bid_time":"2026-10-21T23:15:58.576846779Z",
            "ask_price":"770.480000","venue_ask_time":"2026-10-21T23:15:58.576846779Z",
            "has_traded":true,"state":"active"},
   "close":{"symbol":"SPY","date":"2026-10-20","price":"769.05","interpolated":false,"source":"sip-list-exchange-close"}},
  {"quote":{"symbol":"AAPL","last_trade_price":"344.055000","...":"same shape"},
   "close":{"symbol":"AAPL","date":"2026-10-20","price":"339.5","interpolated":false,"source":"sip-list-exchange-close"}}
]}}
```

Notes: for the current price, use whichever of `last_trade_price` / `last_non_reg_trade_price` has the newer timestamp. For daily change, use `adjusted_previous_close`. `close` is the official prior-session close. Above 20 symbols, `close` is left out and `closes_error` is set. Check `has_traded` and `state == "active"` before using a price.

### Example `get_portfolio` (agent account ••••ACCT)

```json
{"data":{"total_value":"0","equity_value":"0","options_value":"0","futures_value":"0","event_contracts_value":"0",
 "crypto_value":"0","cash":"0","pending_deposits":"0","mutual_funds_value":"0","fixed_income_value":"0","currency":"USD",
 "buying_power":{"buying_power":"0.0000","unleveraged_buying_power":"0.0000","display_currency":"USD"},
 "crypto_buying_power":{"buying_power":"0.0000"}}}
```

The account is unfunded, which is expected during paper mode.

### Example `get_trade_approval_setting` (agent account)

```json
{"data":{"setting":{"account_number":"••••ACCT","human_must_approve_trades":false,"updated_at":"2026-10-21T23:14:07Z"}}}
```

### Example `get_equity_fundamentals` (abridged)

```json
{"symbol":"AAPL","open":"339.280000","high":"345.250000","low":"338.830000","volume":"35601064.000000","market_date":"2026-10-21",
 "average_volume":"39244519.013523","average_volume_30_days":"36830583.356100",
 "high_52_weeks":"348.149900","low_52_weeks":"243.420000","market_cap":"5021207481000.000000",
 "pe_ratio":"38.918758","pb_ratio":"46.128500","shares_outstanding":"14594200000.000000","float":"14576745336.800001",
 "sector":"Electronic Technology","industry":"Telecommunications Equipment","...":"dividend + profile fields"}
```

Symbols that don't resolve come back in `not_found`. Up to 10 symbols per call.

### Example `review_equity_order`

```
(not yet captured: the operator said to wait. With $0 buying power, expect a buying-power alert.)
```

Parameters: `account_number` (must be the agent account), `symbol`, `side` (buy/sell), `type` (market/limit/stop_market/stop_limit), exactly one of `quantity` | `dollar_amount` (dollar only with market), `limit_price`, `stop_price`, `time_in_force` (gfd/gtc), `market_hours` (regular_hours/extended_hours/all_day_hours), optional `tax_lots` (sell only).

### `create_scan` parameters (schema only, not called)

```
create_scan(preset?, filters?, columns?, title?, scan_id?)
  preset:  INITIAL | DAILY_GAINERS | DAILY_LOSERS | HIGH_OPTIONS_VOLUME_IV | UPCOMING_EARNINGS
  filters: enum   -> {filter_type, predicate, values[], interval?, length?, plot?}
           expr   -> {expression, predicate, values[], display_title?}   (validate with preview_scan first)
  columns: {display_name, expression?, order?, visible?}
  scan_id: appends a new config version (REPLACE semantics)
Example: {"filter_type":"FILTER_TYPE_RSI","predicate":">","values":["70"],"interval":"1d","length":14}

PERCENTAGE filters take decimals: 0.05 = 5%. A whole number like 5 reads as 500% and silently matches nothing.
If a filter lists supported_intervals, pass an interval or it can return no results.
To limit a scan to named tickers or index members, use an expression filter on `symbol` (see get_scanner_datapoints).
```

Enum filters relevant to momentum (from `get_scanner_filter_specs`):

```
FILTER_TYPE_INSTRUMENT_TYPE  options: STOCK, ETF, CRYPTO, FUTURE      predicates: =, ANY_OF
FILTER_TYPE_SECTOR           options: Basic Materials, Consumer Cyclical, Financial Services, Real Estate,
                                      Consumer Defensive, Healthcare, Utilities, Communication Services,
                                      Energy, Industrials, Technology
FILTER_TYPE_MARKET_CAP       DOLLAR int
FILTER_TYPE_EARNINGS_DATE    DATETIME
FILTER_TYPE_PERCENT_CHANGE_FROM_CLOSE  PERCENTAGE; intervals 1m..1mo; plots High/Low/Open/Close
FILTER_TYPE_VOLUME, FILTER_TYPE_AVERAGE_VOLUME, FILTER_TYPE_RELATIVE_VOLUME (lengths 1..90)
FILTER_TYPE_HIGH / FILTER_TYPE_LOW   lengths 1,2,3,4,5,6,15,30,52; intervals 1m,1h,1d,1w,1mo
FILTER_TYPE_EMA              lengths 2..200 (incl. 10,20,50,100,150,200); intervals 1m..1mo
FILTER_TYPE_RSI              lengths 2..30; FILTER_TYPE_MACD; FILTER_TYPE_AVERAGE_TRUE_RANGE (10,14,20,25)
FILTER_TYPE_AVERAGE_DIRECTIONAL_INDEX, FILTER_TYPE_VWAP, FILTER_TYPE_LAST, FILTER_TYPE_CLOSE
Also: EPS, Forward P/E, P/E, PEG, margins, ROA/ROE, float, shares outstanding, gap, bid/ask,
      Bollinger, CCI, Aroon, stochastic, support/resistance, Williams %R, option-volume/IV filters.
```

There's no enum filter for leveraged/inverse ETFs (VERIFY #6 is still open).
