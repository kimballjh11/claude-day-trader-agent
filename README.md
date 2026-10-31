# Paper Trader

Private paper-first trading robot for a separate Robinhood Agentic account. Spec: [`TRADING_BOT_MASTER_SPEC.md`](TRADING_BOT_MASTER_SPEC.md).

**Disclaimer:** Experimental. Not financial advice. Public Claude trading tests have lost money. Small separate account only.

## Status

Paper mode active. Cloud routines (Phase A/B + weekly) are on. Do **not** fund the agent account or flip live until graduation — checklist in [`docs/ops.md`](docs/ops.md).

## Docs that matter

| File | What |
|---|---|
| `CLAUDE.md` | Hard rules every agent run |
| `docs/verified.md` | VERIFY results + cloud status |
| `docs/ops.md` | Schedules, lock tests, go-live |
| `docs/mcp_tools.md` | Robinhood MCP tool catalog |
| `PHASE_*_TASK.md` / `WEEKLY_REVIEW_TASK.md` | What each scheduled run does |

## Dashboard

Vercel deployment (your login only): PAPER/LIVE badge, books, votes, graduation checklist. Refreshes after each scheduled run.

## Agent handoffs

If a build session stops near a usage limit, read the newest file in [`docs/handoffs/`](docs/handoffs/).
