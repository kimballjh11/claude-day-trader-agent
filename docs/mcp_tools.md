# Robinhood MCP tools

Server: `robinhood-trading` → `https://agent.robinhood.com/mcp/trading`  
Claude Code / cloud prefix: `mcp__robinhood-trading__<tool>`  
Captured: 2026-10-21 from live Claude Code schemas. Cloud smoke (2026-10-22) saw the same prefix (74 tools visible; place/cancel absent via deny).

## Safety (this repo)

Denied in `.claude/settings.json` (equity place stays denied until M11):

- `place_equity_order`, `cancel_equity_order`
- option place/cancel/review/exercise
- crypto place/cancel

`order_guard.py` also matches `place_*`, `cancel_*`, and `exercise_*`.

Live response shapes (VERIFY #2) go in `docs/verified.md`, not here. Samples below are **request** argument examples only.

---


## Summary

| # | Tool | Kind | Permission | Scope |
|---|---|---|---|---|
| 1 | get_accounts | read | allow | in |
| 2 | get_portfolio | read | allow | in |
| 3 | get_equity_positions | read | allow | in |
| 4 | get_equity_tax_lots | read | default | in |
| 5 | get_limited_margin_upgrade_info | read | default | out |
| 6 | get_trade_approval_setting | read | default | in |
| 7 | get_trade_approvals | read | default | in |
| 8 | decline_trade_approval | write | default | in |
| 9 | get_equity_quotes | read | allow | in |
| 10 | get_equity_price_book | read | default | in |
| 11 | get_equity_historicals | read | allow | in |
| 12 | get_equity_technical_indicators | read | default | in |
| 13 | get_equity_fundamentals | read | allow | in |
| 14 | get_equity_tradability | read | allow | in |
| 15 | get_equity_analyst_ratings | read | default | in |
| 16 | get_financials | read | default | in |
| 17 | get_earnings_calendar | read | allow | in |
| 18 | get_earnings_results | read | allow | in |
| 19 | get_politician_trades | read | default | in |
| 20 | search | read | allow | in |
| 21 | get_equity_orders | read | allow | in |
| 22 | review_equity_order | simulate | allow | in |
| 23 | place_equity_order | **live order** | **deny** | in (live only) |
| 24 | cancel_equity_order | **live order** | **deny** | in (live only) |
| 25 | get_realized_pnl | read | allow | in |
| 26 | get_pnl_trade_history | read | allow | in |
| 27 | get_indexes | read | default | in |
| 28 | get_index_quotes | read | default | in |
| 29 | get_index_historicals | read | default | in |
| 30 | get_sec_filing_index | read | default | in |
| 31 | get_sec_filing | read | default | in |
| 32 | get_sec_filing_facts | read | default | in |
| 33 | get_sec_filing_facts_catalog | read | default | in |
| 34 | get_scans | read | allow | in |
| 35 | run_scan | read | allow | in |
| 36 | preview_scan | read | default | in |
| 37 | create_scan | write | ask | in |
| 38 | update_scan_filters | write | default | in |
| 39 | update_scan_config | write | default | in |
| 40 | get_scanner_filter_specs | read | default | in |
| 41 | get_scanner_datapoints | read | default | in |
| 42 | get_watchlists | read | default | in |
| 43 | get_watchlist_items | read | default | in |
| 44 | get_popular_watchlists | read | default | in |
| 45 | create_watchlist | write | default | in |
| 46 | update_watchlist | write | ask | in |
| 47 | add_to_watchlist | write | default | in |
| 48 | remove_from_watchlist | write | default | in |
| 49 | follow_watchlist | write | default | in |
| 50 | unfollow_watchlist | write | default | in |
| 51 | get_alerts | read | default | in |
| 52 | get_alert_log | read | default | in |
| 53 | create_alert | write | default | in |
| 54 | update_alert | write | default | in |
| 55 | delete_alert | write | default | in |
| 56 | mark_alerts_read | write | default | in |
| 57 | get_legend_layouts | read | default | in |
| 58 | get_legend_charts | read | default | in |
| 59 | get_legend_indicators | read | default | in |
| 60 | get_legend_indicator_catalog | read | default | in |
| 61 | add_legend_indicator | write | default | in |
| 62 | update_legend_indicator | write | default | in |
| 63 | remove_legend_indicator | write | default | in |
| 64 | set_legend_chart_settings | write | default | in |
| 65 | get_option_chains | read | default | out |
| 66 | get_option_instruments | read | default | out |
| 67 | get_option_quotes | read | default | out |
| 68 | get_option_historicals | read | default | out |
| 69 | get_option_positions | read | default | out |
| 70 | get_option_orders | read | default | out |
| 71 | get_option_watchlist | read | default | out |
| 72 | add_option_to_watchlist | write | default | out |
| 73 | remove_option_from_watchlist | write | default | out |
| 74 | get_option_level_upgrade_info | read | default | out |
| 75 | exercise_option | **real money** | default | out |
| 76 | cancel_option_exercise | write | default | out |
| 77 | review_option_order | simulate | **deny** | out |
| 78 | place_option_order | **live order** | **deny** | out |
| 79 | cancel_option_order | **live order** | **deny** | out |
| 80 | get_crypto_account_onboarding_info | read | default | out |
| 81 | get_currency_pairs | read | default | out |
| 82 | get_crypto_quotes | read | default | out |
| 83 | get_crypto_positions | read | default | out |
| 84 | get_crypto_orders | read | default | out |
| 85 | preview_crypto_order | simulate | default | out |
| 86 | place_crypto_order | **real money** | default | out |
| 87 | cancel_crypto_order | **live order** | default | out |

> **Gap worth closing:** `place_crypto_order`, `cancel_crypto_order`, and `exercise_option` move real money but are not in the deny list. The `order_guard.py` hook matches `place_*` / `cancel_*`, so the two crypto order tools are guarded; `exercise_option` is not matched by that hook. Consider adding all three to `deny` (the operator edits `.claude/` by hand).

---

## 1. Account and portfolio

### 1. `get_accounts`
Lists brokerage accounts. `agentic_allowed` marks the one account the agent may trade. Not a reliable source for buying power (use `get_portfolio`).
```json
{}
```

### 2. `get_portfolio`
Market value by asset type, plus buying power.
Params: `account_number`*
```json
{ "account_number": "<ACCOUNT_NUMBER>" }
```

### 3. `get_equity_positions`
Open stock/ETF positions: symbol, quantity, average cost, holds.
Params: `account_number`*, `cursor`
```json
{ "account_number": "<ACCOUNT_NUMBER>" }
```

### 4. `get_equity_tax_lots`
Open tax lots for one holding (quantity, cost basis, acquisition date, short/long term).
Params: `account_number`*, `symbol`*, `cursor`
```json
{ "account_number": "<ACCOUNT_NUMBER>", "symbol": "AAPL" }
```

### 5. `get_limited_margin_upgrade_info`
Checks eligibility for limited margin and returns upgrade links. **Out of scope (margin).**
Params: `account_number`*
```json
{ "account_number": "<ACCOUNT_NUMBER>" }
```

### 6. `get_trade_approval_setting`
Whether trades on the agentic account need manual approval in the app. Read-only; only the customer can change it.
Params: `account_number`* (alphanumeric)
```json
{ "account_number": "<ACCOUNT_NUMBER>" }
```

### 7. `get_trade_approvals`
Pending approvals waiting on the customer, or specific approvals by id in any state.
Params: `account_number`*, `asset_class` (`ASSET_CLASS_EQUITY` | `ASSET_CLASS_OPTION` | `ASSET_CLASS_CRYPTO`), `approval_ids` (≤100), `cursor`
```json
{ "account_number": "<ACCOUNT_NUMBER>", "asset_class": "ASSET_CLASS_EQUITY" }
```

### 8. `decline_trade_approval`
Declines one pending approval so it won't execute. The agent can decline but never approve.
Params: `account_number`*, `approval_id`*
```json
{ "account_number": "<ACCOUNT_NUMBER>", "approval_id": "<APPROVAL_ID>" }
```

---

## 2. Equity market data

### 9. `get_equity_quotes`
Real-time quotes plus the last completed session's official close. Above 20 symbols, `closes` is omitted.
Params: `symbols`*
```json
{ "symbols": ["AAPL", "MSFT", "SPY"] }
```

### 10. `get_equity_price_book`
Level 2 bid/ask ladder snapshot. Max 4 symbols.
Params: `symbols`*
```json
{ "symbols": ["NVDA"] }
```

### 11. `get_equity_historicals`
OHLCV bars over a time range. Interval auto-selects (~2,500 bars) if omitted.
Params: `symbols`* (≤10), `start_time`* (RFC3339 UTC), `end_time`, `interval` (`15second` … `minute`, `5minute`, `hour`, `day`, `week`, …), `bounds` (`regular` default, `extended`, `trading`, `24_5`, `24_7`, `hyper_trading`), `adjustment_type` (`none`, `split` default, `all`)
```json
{
  "symbols": ["AAPL", "MSFT"],
  "start_time": "2026-04-01T00:00:00Z",
  "end_time": "2026-10-20T21:00:00Z",
  "interval": "day",
  "bounds": "regular",
  "adjustment_type": "split"
}
```

### 12. `get_equity_technical_indicators`
Computes an indicator over OHLCV bars for up to 10 symbols.
Params: `type`*, `interval`*, `start_time`*, `symbols` (≤10), `end_time`, `output` (`series` | `latest` | `last:N`), `period`, `fast_period`, `slow_period`, `signal_period`, `num_std`, `multiplier`, `method`, `bounds`, `adjustment_type`. `symbol` is deprecated.
Types: `ema`, `sma`, `rsi`, `momentum`, `roc`, `cci`, `williams_r`, `atr`, `mfi`, `adx`, `donchian_channels`, `bollinger_bands`, `macd`, `keltner_channels`, `supertrend`, `vwap`, `obv`, `pivot_points`.
```json
{
  "type": "rsi",
  "period": 14,
  "interval": "day",
  "start_time": "2026-06-01T00:00:00Z",
  "symbols": ["AAPL", "MSFT", "NVDA"],
  "output": "latest"
}
```
MACD variant:
```json
{
  "type": "macd",
  "fast_period": 12, "slow_period": 26, "signal_period": 9,
  "interval": "day",
  "start_time": "2026-05-01T00:00:00Z",
  "symbols": ["SPY"],
  "output": "last:5"
}
```

### 13. `get_equity_fundamentals`
Valuation, market cap, float, today's OHLCV, volume averages, 52-week range, dividends, profile. Max 10 symbols.
Params: `symbols`*, `bounds` (`regular` default, `trading`, `extended`, `24_5`)
```json
{ "symbols": ["AAPL", "COST"], "bounds": "regular" }
```

### 14. `get_equity_tradability`
Per-session eligibility and fractional support for up to 10 symbols on an account.
Params: `account_number`*, `symbols`*
```json
{ "account_number": "<ACCOUNT_NUMBER>", "symbols": ["AAPL", "QQQ"] }
```

### 15. `get_equity_analyst_ratings`
Analyst price targets (high/low/avg) and Buy/Hold/Sell counts. Max 75 symbols.
Params: `symbols`*
```json
{ "symbols": ["AAPL", "AMZN"] }
```

### 16. `get_financials`
Revenue, gross profit, net income, net margin by fiscal period.
Params: `symbols`* (≤20), `period` (`quarterly` default | `annual`), `limit` (default 4, max 40)
```json
{ "symbols": ["MSFT"], "period": "quarterly", "limit": 8 }
```

### 17. `get_earnings_calendar`
Market-wide earnings over a window of up to 31 days.
Params: `start_date` (YYYY-MM-DD, default today ET), `days` (−31…31, default 7), `filter` (`high_market_cap`)
```json
{ "start_date": "2026-10-21", "days": 7, "filter": "high_market_cap" }
```

### 18. `get_earnings_results`
Up to 8 trailing quarters plus upcoming earnings for one symbol.
Params: `symbol`*
```json
{ "symbol": "NVDA" }
```

### 19. `get_politician_trades`
STOCK Act disclosures (via TipRanks). Amounts are ranges; disclosures lag up to 45 days. Pass at least one parameter.
Params: `equity_symbol`, `politician_name`
```json
{ "equity_symbol": "NVDA" }
```

### 20. `search`
Resolves a name or partial ticker to stocks/ETFs, crypto pairs, or indexes.
Params: `query`*, `asset_type` (`instrument` default | `currency_pair` | `market_index`), `limit` (default 10, max 20)
```json
{ "query": "costco", "asset_type": "instrument", "limit": 5 }
```

---

## 3. Equity orders and P&L

### 21. `get_equity_orders`
Order history (newest first), or a single order by `order_id`.
Params: `account_number`*, `order_id`, `symbol`, `state` (`new`, `queued`, `confirmed`, `unconfirmed`, `partially_filled`, `filled`, `cancelled`, `rejected`, `failed`, `voided`), `created_at_gte`, `agent_initiated`, `placed_agent`, `cursor`
```json
{
  "account_number": "<ACCOUNT_NUMBER>",
  "state": "filled",
  "created_at_gte": "2026-10-14T00:00:00Z",
  "agent_initiated": true
}
```

### 22. `review_equity_order`
Simulates a stock order without placing it. Returns the quote and pre-trade alerts (buying power, PDT, halts). Needs an `agentic_allowed=true` account.
Params: `account_number`*, `symbol`*, `side`* (`buy`|`sell`), `type`* (`market`|`limit`|`stop_market`|`stop_limit`), `quantity` **or** `dollar_amount` (market only), `limit_price`, `stop_price`, `time_in_force` (`gfd` default | `gtc`), `market_hours` (`regular_hours` default | `extended_hours` | `all_day_hours`), `tax_lots` (sell only)
```json
{
  "account_number": "<ACCOUNT_NUMBER>",
  "symbol": "AAPL",
  "side": "buy",
  "type": "limit",
  "quantity": "2",
  "limit_price": "231.50",
  "time_in_force": "gfd",
  "market_hours": "regular_hours"
}
```
Stop-loss sell variant:
```json
{
  "account_number": "<ACCOUNT_NUMBER>",
  "symbol": "AAPL",
  "side": "sell",
  "type": "stop_market",
  "quantity": "2",
  "stop_price": "218.00",
  "time_in_force": "gtc"
}
```

### 23. `place_equity_order` — **DENIED**
Places a real stock order. Denied in settings and guarded by `.claude/hooks/order_guard.py`, so its schema is hidden from the agent. Per the `review_equity_order` docs it takes the same parameters plus an idempotency `ref_id`. The shape below is **inferred and unverified**:
```json
{
  "account_number": "<ACCOUNT_NUMBER>",
  "symbol": "AAPL",
  "side": "buy",
  "type": "limit",
  "quantity": "2",
  "limit_price": "231.50",
  "time_in_force": "gfd",
  "market_hours": "regular_hours",
  "ref_id": "<NEW_UUID>"
}
```

### 24. `cancel_equity_order` — **DENIED**
Cancels an open stock order. Schema is hidden. **Inferred** shape, modeled on `cancel_crypto_order`:
```json
{ "account_number": "<ACCOUNT_NUMBER>", "order_id": "<ORDER_ID>" }
```

### 25. `get_realized_pnl`
Bucketed realized P&L totals over a window.
Params: `account_number`* (rhs number), `span` (`day`, `week`, `month`, `3month` default, `year`, `all`) **or** `start_date`+`end_date`, `asset_classes` (`equity`, `option`, `crypto`), `timezone`, `display_currency` (USD)
```json
{ "account_number": "<RHS_ACCOUNT_NUMBER>", "span": "month", "asset_classes": ["equity"] }
```

### 26. `get_pnl_trade_history`
Per-trade realized P&L list.
Params: `account_number`* (rhs number), `span` (`week` default, `month`, `3month`, `ytd`, `all`), `symbol`, `cursor`
```json
{ "account_number": "<RHS_ACCOUNT_NUMBER>", "span": "month" }
```

---

## 4. Indexes

### 27. `get_indexes`
Index metadata and UUIDs. Omit `symbols` to list all.
Params: `symbols` (comma-separated string)
```json
{ "symbols": "SPX,NDX,DJI" }
```

### 28. `get_index_quotes`
Current index levels.
Params: `instrument_ids`* (from `get_indexes`)
```json
{ "instrument_ids": ["<SPX_INDEX_ID>"] }
```

### 29. `get_index_historicals`
Index OHLC bars. `interval` is required, with no auto-select.
Params: `instrument_ids`* (≤10), `start_time`*, `interval`*, `end_time`
```json
{
  "instrument_ids": ["<SPX_INDEX_ID>"],
  "start_time": "2026-07-01T00:00:00Z",
  "interval": "day"
}
```

---

## 5. SEC filings

### 30. `get_sec_filing_index`
Lists a company's filings.
Params: `symbol`*, `form_type` (array), `since`, `until`, `cursor`
```json
{ "symbol": "AAPL", "form_type": ["10-K", "10-Q"], "since": "2025-01-01" }
```

### 31. `get_sec_filing`
A filing's table of contents, or one section's text.
Params: `filing_id`*, `section`
```json
{ "filing_id": "<FILING_ID>", "section": "<SECTION_ID>" }
```

### 32. `get_sec_filing_facts`
Tagged GAAP facts from 1–3 filings.
Params: `filing_ids`* (1–3), `concepts`* (1–10)
```json
{ "filing_ids": ["<FILING_ID>"], "concepts": ["Revenues", "NetIncomeLoss", "Assets"] }
```

### 33. `get_sec_filing_facts_catalog`
Distinct GAAP concepts in a filing. Use it after a direct facts guess comes back empty.
Params: `filing_id`*, `concept_contains`, `axis_name_in`, `offset`
```json
{ "filing_id": "<FILING_ID>", "concept_contains": "Debt" }
```

---

## 6. Scanners (screeners)

### 34. `get_scans`
The user's saved scans with filters, columns, sort, and the `cortex_managed` flag.
```json
{}
```

### 35. `run_scan`
Runs a saved scan against live data.
Params: `scan_id`*
```json
{ "scan_id": "<SCAN_ID>" }
```

### 36. `preview_scan`
Runs a filter set live **without saving**. Use it to validate before `create_scan`.
Params: `filters`* (non-empty), `columns`
```json
{
  "filters": [
    { "filter_type": "FILTER_TYPE_RSI", "predicate": "PREDICATE_GREATER_THAN", "values": ["70"], "interval": "1d", "length": 14 },
    {
      "expression": "dayVolume / volumeAvg(candleCount=30, candlePeriod=\"1d\", session=\"all\")",
      "predicate": "PREDICATE_GREATER_THAN_OR_EQUAL",
      "values": ["1.5"],
      "display_title": "Relative volume (30D)"
    }
  ],
  "columns": [{ "display_name": "Market cap" }]
}
```

### 37. `create_scan`
Saves a new scan, or appends a new config version to an existing one when `scan_id` is passed (REPLACE semantics).
Params: `preset` (`INITIAL`, `DAILY_GAINERS`, `DAILY_LOSERS`, `HIGH_OPTIONS_VOLUME_IV`, `UPCOMING_EARNINGS`), `filters`, `columns`, `title`, `scan_id`
```json
{
  "preset": "INITIAL",
  "title": "High RSI + High Volume",
  "filters": [
    { "filter_type": "FILTER_TYPE_RSI", "predicate": ">", "values": ["70"], "interval": "1d", "length": 14 },
    { "filter_type": "FILTER_TYPE_VOLUME", "predicate": ">", "values": ["1000000"], "interval": "1d" }
  ]
}
```

### 38. `update_scan_filters`
Replaces a saved scan's enum filters. Rejects expression filters; use `create_scan` with `scan_id` for those. Send `[]` to clear.
Params: `scan_id`*, `filters`*
```json
{
  "scan_id": "<SCAN_ID>",
  "filters": [
    { "filter_type": "FILTER_TYPE_RSI", "predicate": "PREDICATE_GREATER_THAN", "values": ["60"], "interval": "1d", "length": 14 }
  ]
}
```

### 39. `update_scan_config`
Changes sort order and/or replaces extra columns. Filters are preserved.
Params: `scan_id`*, `sorting_column`, `sorting_direction` (`asc`|`desc`), `columns`
```json
{ "scan_id": "<SCAN_ID>", "sorting_column": "% Change", "sorting_direction": "desc" }
```

### 40. `get_scanner_filter_specs`
Every valid `FILTER_TYPE_*` with its predicates, intervals, lengths, and plots.
```json
{}
```

### 41. `get_scanner_datapoints`
Expression functions and fields for one category.
Params: `category`* (`technical`, `price_volume`, `fundamental`, `options`, `volatility`, `quote`, `descriptive`, or `function`/`field`)
```json
{ "category": "price_volume" }
```

---

## 7. Watchlists

### 42. `get_watchlists`
The user's custom and followed lists, with their `list_id`s.
```json
{}
```

### 43. `get_watchlist_items`
Items in one list (stocks, crypto, indexes). For options, use `get_option_watchlist`.
Params: `list_id`*
```json
{ "list_id": "<LIST_ID>" }
```

### 44. `get_popular_watchlists`
Robinhood-curated lists available to follow.
```json
{}
```

### 45. `create_watchlist`
Creates a custom list.
Params: `display_name`*, `display_description`, `icon_emoji`
```json
{ "display_name": "Momentum Candidates", "display_description": "Phase A shortlist", "icon_emoji": "🚀" }
```

### 46. `update_watchlist`
Renames a custom list or changes its icon/description.
Params: `list_id`*, `display_name`, `display_description`, `icon_emoji`
```json
{ "list_id": "<LIST_ID>", "display_name": "Momentum Shortlist" }
```

### 47. `add_to_watchlist`
Adds items. Pass exactly one of `symbols`, `currency_pair_ids`, or `index_ids`.
Params: `list_id`*, plus one of the above
```json
{ "list_id": "<LIST_ID>", "symbols": ["AAPL", "NVDA"] }
```

### 48. `remove_from_watchlist`
Removes items, with the same one-of rule as `add_to_watchlist`.
```json
{ "list_id": "<LIST_ID>", "symbols": ["AAPL"] }
```

### 49. `follow_watchlist`
Follows a curated list.
Params: `list_id`*
```json
{ "list_id": "<CURATED_LIST_ID>" }
```

### 50. `unfollow_watchlist`
Stops following a curated list.
Params: `list_id`*
```json
{ "list_id": "<CURATED_LIST_ID>" }
```

---

## 8. Alerts

### 51. `get_alerts`
Configured price/indicator alerts.
Params: `symbol`, `asset_class` (only with `symbol`), `cursor`
```json
{ "symbol": "AAPL" }
```

### 52. `get_alert_log`
Fired alerts with read/unread state. Alerts are not pushed, so poll this.
Params: `asset_class`, `since`, `limit` (1–100, default 20), `cursor`
```json
{ "asset_class": "equity", "since": "2026-10-20T00:00:00Z", "limit": 50 }
```

### 53. `create_alert`
Creates a price or indicator alert. Price-vs-line conditions take no `threshold`.
Params: `symbol`*, `condition_type`*, `threshold`, `indicator` {`interval_secs`*, `period`, `fast_period`, `slow_period`, `signal_period`, `std_dev`, `ma_type`}, `asset_class`
Price alert:
```json
{ "symbol": "AAPL", "condition_type": "price_below", "threshold": "215.00" }
```
Price crosses the 50-day SMA:
```json
{
  "symbol": "AAPL",
  "condition_type": "price_crosses_sma",
  "indicator": { "period": 50, "interval_secs": 86400 }
}
```

### 54. `update_alert`
Enables/disables an alert or adjusts it within the same condition family.
Params: `alert_id`*, `enabled`, `condition_type`, `threshold`, `indicator`
```json
{ "alert_id": "<ALERT_ID>", "enabled": false }
```

### 55. `delete_alert`
Two-step delete: the first call (no `confirm`) previews; the second, with `confirm: true`, deletes.
Params: `alert_id`*, `confirm`
```json
{ "alert_id": "<ALERT_ID>" }
```
```json
{ "alert_id": "<ALERT_ID>", "confirm": true }
```

### 56. `mark_alerts_read`
Pass exactly one of `alert_log_ids` (≤100) or `all_through` (never a future time).
```json
{ "alert_log_ids": ["<ALERT_LOG_ID_1>", "<ALERT_LOG_ID_2>"] }
```

---

## 9. Legend (charting workspace)

### 57. `get_legend_layouts`
Saved layouts and their widgets.
```json
{}
```

### 58. `get_legend_charts`
Open charts with their `chart_id`, symbol, interval, timeframe, and type.
```json
{}
```

### 59. `get_legend_indicators`
Indicators applied to each open chart, with their `indicator_id`s.
```json
{}
```

### 60. `get_legend_indicator_catalog`
Built-in indicators with their parameters and defaults.
```json
{}
```

### 61. `add_legend_indicator`
Adds an indicator to one chart. Limits: 10 per chart, at most 5 in lower panes.
Params: `chart_id`*, `indicator`* (catalog id), `parameters` [{`name`, `value`}]
```json
{
  "chart_id": "<CHART_ID>",
  "indicator": "<CATALOG_INDICATOR_ID>",
  "parameters": [{ "name": "length", "value": "21" }]
}
```

### 62. `update_legend_indicator`
Changes an applied indicator's params, visibility, or plot styling.
Params: `indicator_id`*, `parameters`, `visible`, `plots` [{`plot`*, `color`, `style`, `thickness` 1–5}]
```json
{
  "indicator_id": "<INDICATOR_ID>",
  "parameters": [{ "name": "length", "value": "50" }],
  "plots": [{ "plot": "<PLOT_NAME>", "color": "Dark Blue", "thickness": 2 }]
}
```

### 63. `remove_legend_indicator`
Removes an applied indicator from its chart.
Params: `indicator_id`*
```json
{ "indicator_id": "<INDICATOR_ID>" }
```

### 64. `set_legend_chart_settings`
Changes a chart's interval, timeframe, or chart type. It cannot change the symbol.
Params: `chart_id`*, `interval` {`amount`, `unit`}, `timeframe` (`1d`, `1w`, `1mo`, `3mo`, `ytd`, `1y`, `5y`, `all`), `chart_type` (`candle`, `bar`, `line`, `area`, `heikinAshi`, …)
```json
{
  "chart_id": "<CHART_ID>",
  "interval": { "amount": 1, "unit": "day" },
  "timeframe": "3mo",
  "chart_type": "candle"
}
```

---

## 10. Options — out of scope for this bot

### 65. `get_option_chains`
Params: `underlying_symbol` or `ids`
```json
{ "underlying_symbol": "AAPL" }
```

### 66. `get_option_instruments`
Params: one of `chain_symbol`/`chain_id`/`ids`; plus `expiration_dates`, `strike_price`, `type` (`call`|`put`), `state`, `tradability`, `cursor`
```json
{ "chain_symbol": "AAPL", "expiration_dates": "2026-11-20", "type": "call", "strike_price": "240.0000" }
```

### 67. `get_option_quotes`
Params: `instrument_ids`*
```json
{ "instrument_ids": ["<OPTION_ID>"] }
```

### 68. `get_option_historicals`
Params: `instrument_ids`* (≤10), `start_time`*, `end_time`, `interval`, `bounds`
```json
{ "instrument_ids": ["<OPTION_ID>"], "start_time": "2026-10-01T00:00:00Z", "interval": "hour" }
```

### 69. `get_option_positions`
Params: `account_number`*, `nonzero`, `chain_ids`, `option_ids`, `option_type`, `type`, `expiration_date`, `expiration_date_gte`, `expiration_date_lte`, `cursor`
```json
{ "account_number": "<ACCOUNT_NUMBER>", "nonzero": true }
```

### 70. `get_option_orders`
Params: `account_number`*, `order_id`, `state`, `chain_ids`, `created_at_gte`, `underlying_type`, `agent_initiated`, `placed_agent`, `cursor`
```json
{ "account_number": "<ACCOUNT_NUMBER>", "state": "filled" }
```

### 71. `get_option_watchlist`
```json
{}
```

### 72. `add_option_to_watchlist`
Params: `option_ids`*, `position_type` (`long` default | `short`)
```json
{ "option_ids": ["<OPTION_ID>"], "position_type": "long" }
```

### 73. `remove_option_from_watchlist`
Params: `option_ids`*, `position_type`
```json
{ "option_ids": ["<OPTION_ID>"] }
```

### 74. `get_option_level_upgrade_info`
Params: `account_number`*
```json
{ "account_number": "<ACCOUNT_NUMBER>" }
```

### 75. `exercise_option` — **real money, not denied**
Params: `account_number`*, `option_id`*, `quantity`*, `allow_shorts`, `reason`, `ref_id`
```json
{ "account_number": "<ACCOUNT_NUMBER>", "option_id": "<OPTION_ID>", "quantity": 1, "ref_id": "<NEW_UUID>" }
```

### 76. `cancel_option_exercise`
Params: `account_number`*, `option_id`*
```json
{ "account_number": "<ACCOUNT_NUMBER>", "option_id": "<OPTION_ID>" }
```

### 77. `review_option_order` — **DENIED** (schema hidden)
### 78. `place_option_order` — **DENIED** (schema hidden)
### 79. `cancel_option_order` — **DENIED** (schema hidden)

No sample payloads: these schemas are hidden from the agent, and the tools are out of scope anyway.

---

## 11. Crypto — out of scope for this bot

Crypto tools take the **numeric** `rhs_account_number`, not `account_number`.

### 80. `get_crypto_account_onboarding_info`
```json
{}
```

### 81. `get_currency_pairs`
Params: `limit` (1–700, default 25), `cursor`
```json
{ "limit": 25 }
```

### 82. `get_crypto_quotes`
Params: `symbols`*, `rhs_account_number`, `timezone` (IANA name)
```json
{ "symbols": ["BTC-USD", "ETH-USD"] }
```

### 83. `get_crypto_positions`
Params: `rhs_account_number`*, `cursor`
```json
{ "rhs_account_number": "<RHS_ACCOUNT_NUMBER>" }
```

### 84. `get_crypto_orders`
Params: `rhs_account_number`*, `order_id`, `symbol`, `side`, `state`, `state_group` (`open`|`closed`), `created_at_gte`, `updated_at_gte`, `cursor`
```json
{ "rhs_account_number": "<RHS_ACCOUNT_NUMBER>", "state_group": "open" }
```

### 85. `preview_crypto_order`
Params: `rhs_account_number`*, `symbol`*, `side`*, `type`* (`market`, `limit`, `stop_loss`, `stop_limit`), `quantity` **or** `dollar_amount`, `limit_price`, `stop_price`, `time_in_force` (`gtc`, `gfd`, `gfw`, `gfm`), `tax_lots`
```json
{ "rhs_account_number": "<RHS_ACCOUNT_NUMBER>", "symbol": "BTC", "side": "buy", "type": "market", "dollar_amount": "25.00" }
```

### 86. `place_crypto_order` — **real money, not denied** (hook-guarded)
Same params as the preview, plus `ref_id`.
```json
{ "rhs_account_number": "<RHS_ACCOUNT_NUMBER>", "symbol": "BTC", "side": "buy", "type": "market", "dollar_amount": "25.00", "ref_id": "<NEW_UUID>" }
```

### 87. `cancel_crypto_order` — **not denied** (hook-guarded)
Params: `rhs_account_number`*, `order_id`*
```json
{ "rhs_account_number": "<RHS_ACCOUNT_NUMBER>", "order_id": "<ORDER_ID>" }
```

---

## Notes on referenced-but-absent tools

Some tool descriptions mention tools that this server does **not** expose: `get_advanced_orders`, `get_legend_custom_indicators`, `create_legend_custom_indicator`, `update_legend_custom_indicator`, `get_crypto_tax_lots`, and `get_quotes`. Don't plan on them.
