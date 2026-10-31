# Paper Trader

Paper-first trading robot for a separate Robinhood Agentic account. Spec: [`TRADING_BOT_MASTER_SPEC.md`](TRADING_BOT_MASTER_SPEC.md).

**Disclaimer:** Experimental. Not financial advice. Public Claude trading tests have lost money. Small separate account only.

This repository is an **anonymized public mirror** of a private ops checkout. Personal identifiers, account digits, cloud routine IDs, and live paper-trial history have been removed. Secrets (account number, GitHub token) stay in environment variables — never in the repo.

## Status

Default mode is **paper**. Do **not** fund an agent account or flip live until you complete the graduation checklist in [`docs/ops.md`](docs/ops.md).

## Docs that matter

| File | What |
|---|---|
| `CLAUDE.md` | Hard rules every agent run |
| `docs/verified.md` | VERIFY results + cloud status notes |
| `docs/ops.md` | Schedules, lock tests, go-live |
| `docs/mcp_tools.md` | Robinhood MCP tool catalog |
| `PHASE_*_TASK.md` / `WEEKLY_REVIEW_TASK.md` | What each scheduled run does |
| `NOTICE.md` | Third-party attribution |

## Quick start (local)

```bash
python3 -m unittest discover -s tests -q
python3 scripts/paper_broker.py init --book claude --capital 1000 --date "$(date +%F)"
python3 scripts/paper_broker.py init --book control --capital 1000 --date "$(date +%F)"
```

Wire the official Robinhood MCP (`https://agent.robinhood.com/mcp/trading`) via `.mcp.json`. Set `RH_AGENT_ACCOUNT_NUMBER` only in your local/cloud environment when you are ready for live paths.

## Dashboard

Optional Vercel deploy from `dashboard/` with Deployment Protection on. Vote API needs `GITHUB_TOKEN` and `GITHUB_REPO` as Vercel env vars (never commit them).

## License

MIT, with third-party notices in `NOTICE.md` / `LICENSE`.
