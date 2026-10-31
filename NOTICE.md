# NOTICE — third-party attribution

This project incorporates code and ideas under the licenses below. The authoritative build contract is `TRADING_BOT_MASTER_SPEC.md`.

## FriesTrader (MIT)

- **Source:** https://github.com/YizhiSong/FriesTrader
- **Commit:** `3b9a1d1`
- **Copyright:** (c) 2026 Yizhi Song
- **License text:** root `LICENSE`

Imported as the base: `risk_rules.json` (to be replaced in M2 with the Section 6 file), Phase A/B task drafts, and scripts:

`entry_gate.py`, `stop_loss.py`, `take_profit.py`, `conviction_trim.py`, `rank_candidates.py`, `position_sizing.py`, `pnl_pct.py`

Planned modifications (not yet applied at M1): momentum ranking tiebreak, conviction tiers from config, max-order / sector / session caps (see master spec Sections 7.5–7.6).

## agentic-trading-desk (MIT)

- **Source:** https://github.com/Oft3r/agentic-trading-desk
- **Commit:** `2cdfe07`
- **Copyright:** (c) 2026 Oft3r
- **Files:** `scripts/atd/*` — see `scripts/atd/NOTICE.md` and `scripts/atd/LICENSE`

Order-guard *ideas* from ATD are reimplemented in this repo (Milestone 4); ATD’s “Autonomous Execution Mandate” text is not used.

## rh-trading-agent (MIT)

- **Source:** https://github.com/LoganYangBo/rh-trading-agent
- **Commit:** `639fe3c`
- **Copyright:** (c) 2026 Bo Yang
- **Adapted file:** `.claude/agents/risk-manager.md` (read-only tools, sonnet, rules from `risk_rules.json` / master spec)

Permission-list *structure* ideas inform `.claude/settings.json` (written in Milestone 4). Do not copy `Bash(git push *)` auto-allow patterns beyond what scheduled runs need.

## robinhood-agent (MIT) — ideas / evidence only

- **Source:** https://github.com/alidaftar1/robinhood-agent
- **Commit reviewed:** `11646fd`
- Research findings justify the momentum choice (master spec Section 2). No code copied. Signal-attribution ledger is an idea only.

## Not copied

| Source | Why |
|---|---|
| shameless-clone-agent | No license — ideas only (paper graduation gate) |
| OpenTrade | Elastic License 2.0 — fail-closed gate reimplemented later, no code/text |
| alpaca-mcp-server | Reference only |
| ai-momentum-trader | Explicit anti-pattern set |
