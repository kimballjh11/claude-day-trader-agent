# Ops — schedules, lock tests, go-live

## Schedules (done)

Three Claude Code cloud routines are **active**. Do not create duplicates.

| Name | When (America/Denver) | Prompt file |
|---|---|---|
| `paper-trader-phase-a` | Mon–Fri 3:30pm | `PHASE_A_TASK.md` |
| `paper-trader-phase-b` | Mon–Fri 8:00am | `PHASE_B_TASK.md` |
| `paper-trader-weekly` | Fri 4:30pm | `WEEKLY_REVIEW_TASK.md` |

IDs and cloud MCP notes: `docs/verified.md`.

### DST / UTC crons (apply now — winter UTC)

Routines use **UTC**. Set these now so they stay correct after Sun Nov 1 (MST). Until then, Denver local times run **~1 hour late** (Phase B ≈ 9:00am MDT / 11:00am ET) — acceptable for paper.

In [claude.ai/code/routines](https://claude.ai/code/routines), edit each task’s schedule to:

| Routine | Cron (UTC) | After Nov 1 (MST) | Until Nov 1 (MDT) |
|---|---|---|---|
| phase-b | `0 15 * * 1-5` | 8:00am Denver | ~9:00am Denver |
| phase-a | `30 22 * * 1-5` | 3:30pm Denver | ~4:30pm Denver |
| weekly | `30 23 * * 5` | Fri 4:30pm Denver | ~Fri 5:30pm Denver |

If the UI asks for timezone, prefer **UTC** with the crons above (or America/Denver wall times 8:00 / 15:30 / 16:30 if the product stores local time).

Cloud needs: claude.ai connector `robinhood-trading` + network allow `agent.robinhood.com`. Local Mac `/mcp` does not carry into cloud.

---

## Lock tests

Run in an interactive Claude Code session (before graduation).

### Test 1 — Deny list blocks place

Ask Claude to place a $1 market buy.  
**Expected:** Blocked by deny of `place_equity_order`. **Passed 2026-10-21.**

### Test 2 — Order guard blocks paper mode

On a scratch branch only: move `place_equity_order` from deny to ask → ask for $1 buy → hook denies because `execution.mode` is `"paper"` → revert. Never merge.

### Test 3 — Unit payloads

```bash
python3 -m unittest tests.test_order_guard -v
```

### Test 4 — Cloud place attempt (VERIFY #11)

**Skipped for paper.** Cloud smoke already showed place/cancel tools **absent**. Do not attempt a real place while mode is paper.

---

## Go live (M11) — Operator only

Do this **only after** graduation (master spec §10.6). Cursor never flips these.

1. Confirm Robinhood trade approvals are **off** on the agent account.
2. Fund the agent account with **$1,000**.
3. In GitHub, `risk_rules.json`: `execution.mode` → `"live"`, `autonomy.phase` → `2`.
4. In GitHub, `.claude/settings.json`: move `place_equity_order` from deny to allow; leave `cancel_equity_order` denied.

**Emergency stop:** set `execution.mode` back to `"paper"` in GitHub.

After the first live morning, watch the dashboard for `ROBINHOOD_APPROVAL_REQUIRED` / `ORDER_NOT_CONFIRMED` and record held-order shapes under VERIFY #13 in `docs/verified.md`.
