# the operator's to-do list

_Written 2026-10-21. Paper trial started 2026-10-22._

> **Timing note:** Until Nov 1, every routine fires about an hour later than the dashboard header says. The header reads the times in `risk_rules.json`; the cloud schedules are already set for winter time. Evening runs fire around 4:30pm Mountain, not 3:30pm.

## Before Thursday's runs

- [ ] Push the fixes for conviction caps, the daily loss halt and sizing rounding. The cloud runs only see what's on GitHub, so this must happen before 9am Thursday.

## Thursday, Oct 22

- [ ] **About 9:10am:** check the first Phase B run on GitHub.
  - Look at the new commit, `status/last_run.json` and `recaps/2026-10-22.md` for errors.
  - With no proposals yet, it should just settle, mark the books and record SPY.
- [ ] **About 5–6pm, after the Phase A run** (it fires about 4:30pm Mountain):
  1. Refresh the dashboard. Confirm decisions appear and "Unvoted" is above 0.
  2. Open the browser's developer tools on the Network tab, then click Agree or Disagree on one decision.
  3. The `/api/vote` request should return **200**. If it doesn't, the status code points to the cause:
     - **401 or 403:** Vercel's protection is blocking the API;
     - **404 `decision_not_in_state`:** the deployment has an older `state.json`;
     - **500:** a token or repo setting is wrong.
  4. On GitHub, confirm a new `reviews/votes/<decision_id>.json` file and a `vote: …` commit.
  5. Vote a second time, either a different decision or the same one with the opposite vote. This tests overwriting an existing vote file. Any vote that works also proves voting works with authentication on.
- [ ] **VERIFY #10:** open the dashboard in a private window and confirm Vercel's login blocks it. The vote test only proves voting works while logged in.
- [ ] **Check the leftover weekly run** (session `cse_018UwYmS2RAFiZDRnGJzTkM3`, fired Oct 22 at 01:38 UTC). Make sure it didn't commit anything unexpected.

## Friday, Oct 23

- [ ] The first weekly review runs at about 5:30pm Mountain. Read `reviews/2026-W43.md` and check that the new journal lessons make sense.

## Open bugs: paper trial

- [ ] **Signal attribution will always say "n/a".** Price history is saved in `data/raw/`, which is gitignored, so each cloud run starts without it. Move it to a committed file.
- [ ] **No script converts price data for `momentum.py`.** `prepare_inputs.py` outputs only closes; `momentum.py` needs date, close, volume and high per bar. The agent has to improvise this every evening.
- [ ] **Trading days are counted by hand.** The earnings blackout, re-entry lock, early-exit window and the 1-trading-day proposal expiry all need a trading-day counter script.
- [ ] **Paper buys record the wrong details.** B10's buy command doesn't pass `--stop-pct`, `--asset-type` or `--proposal-id`, so the dashboard shows a 7% stop and labels ETFs as stocks. Trading isn't affected.
- [ ] **The control book can't buy what the claude book holds.** `is_holding` covers both books, which skews the comparison.

## Ongoing through the paper month (ends about Nov 23)

- [ ] Vote on decisions most days. Graduation needs at least 80% coverage.
- [ ] Glance at the dashboard banners after each run for errors, halts and missed runs.
- [ ] Look over any ETF the bot buys. Leveraged and inverse funds are only caught by keyword and `etf_exclusions.csv` (VERIFY #6).
- [ ] Confirm the 2027 holidays on nyse.com (VERIFY #9).
- [ ] After Nov 1, check that the morning run lands at about 8:06am Mountain.
- [ ] **VERIFY #12:** watch Claude usage limits. Three routines a day with up to 30 web searches each could hit them.
- [ ] Mark VERIFY #9 as done in `docs/verified.md` once the 2027 holidays are confirmed. Add 2028 dates before the end of 2027.

## End of the paper month (graduation)

- [ ] Run the lock tests in the last 5 trading days, following `docs/ops.md`. Test 2 is on a scratch branch only.
- [ ] Check every item on the dashboard's "Progress to going live" checklist. "Clean runs" and "Lock tests" are hard-coded as unmet, so check those two yourself.
- [ ] Compare the claude book against the control book and SPY in the weekly reviews.

## Make live mode work (before go-live)

Go-live isn't just config changes. These must be fixed first:

- [ ] **Confirm `place_equity_order` accepts `ref_id` (VERIFY #2).** `review_equity_order` rejects unknown fields and has no `ref_id`; previews already strip it (`live_orders.py --for-review`).
- [ ] **The live book forgets each position's history.** Robinhood's position data has no take-profit tiers, entry date, stop or conviction. Without them:
  - the +15% take-profit would sell 25% again every morning while the gain stays above 15%;
  - the trailing stop, early-exit guard and re-entry lock stop working.
- [ ] **Other parts still read the paper book in live mode.** The loss halts, the dashboard and the audit all read `paper/claude.json`.
- [ ] **The live audit never checks orders against Robinhood.** `audit.py`'s `main()` never passes the broker order list, so that check is skipped.
- [ ] **The order window is tight.** It closes at 11:00 ET and Phase B starts at 10:00 ET, so a slow run would have its buys blocked by the order guard.
- [ ] **Plan the emergency stop.** Switching back to paper stops the bot managing real positions, so they'd have no stop-losses, and it doesn't stop a run that's already in progress.
- [ ] **Rehearse before funding:** run one morning in live mode on a scratch branch, using only `review_equity_order`. Paper mode skips previews, so this is their first real test; capture the buying-power warning text (VERIFY #8).

## Go-live (M11): only after graduation, all done by the operator

- [ ] Re-check that trade approvals are off (step 1 in `docs/ops.md`).
- [ ] Fund the account a few days early so the cash has settled.
- [ ] Capture one `review_equity_order` response to confirm the order fields (VERIFY #2).
- [ ] Set `RH_AGENT_ACCOUNT_NUMBER` in the cloud environment. Never put it in the repo; without it, the order guard blocks every order. Confirm the order guard can see it in a cloud run.
- [ ] Set `execution.mode` to `live` and `autonomy.phase` to `2` in `risk_rules.json`.
- [ ] Move `place_equity_order` off the deny list in `.claude/settings.json`. Leave `cancel_equity_order` denied.
- [ ] **First live morning:**
  - prove the order guard fires in the cloud (VERIFY #11);
  - record what a held order looks like (VERIFY #13);
  - check the live position field names in `book.py` against real `get_equity_positions` data.

**Emergency stop:** set `execution.mode` back to `paper` in GitHub.
