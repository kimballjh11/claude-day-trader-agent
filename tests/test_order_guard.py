#!/usr/bin/env python3
"""Tests for .claude/hooks/order_guard.py."""
import json
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
import order_guard  # noqa: E402

GUARD = ROOT / ".claude" / "hooks" / "order_guard.py"


def rules_live():
    r = json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))
    r = json.loads(json.dumps(r))
    r["execution"]["mode"] = "live"
    r["autonomy"]["phase"] = 2
    return r


AGENT = "TESTACCT1"


def live_buy(**over):
    order = {"account_number": AGENT, "side": "buy", "symbol": "AAPL", "type": "market",
             "dollar_amount": 100, "time_in_force": "gfd", "market_hours": "regular_hours"}
    order.update(over)
    return order


def live_sell(**over):
    order = {"account_number": AGENT, "side": "sell", "symbol": "AAPL", "type": "market",
             "quantity": 1, "time_in_force": "gfd", "market_hours": "regular_hours"}
    order.update(over)
    return order


def weekday_1030_et():
    # 2026-10-21 is a Wednesday
    return datetime(2026, 10, 21, 10, 30, tzinfo=ZoneInfo("America/New_York"))


class TestOrderGuard(unittest.TestCase):
    def test_paper_mode_denies_all(self):
        rules = json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))
        ok, reason = order_guard.evaluate(
            {"side": "buy", "symbol": "AAPL", "type": "market", "dollar_amount": 1,
             "time_in_force": "gfd"},
            rules,
            set(),
            set(),
            now_et=weekday_1030_et(),
        )
        self.assertFalse(ok)
        self.assertIn("live", reason)

    def _eval(self, order, account=AGENT):
        return order_guard.evaluate(order, rules_live(), set(), set(),
                                    now_et=weekday_1030_et(), agent_account=account)

    def test_live_market_buy_allowed(self):
        ok, reason = self._eval(live_buy())
        self.assertTrue(ok, reason)

    def test_live_market_sell_allowed(self):
        ok, reason = self._eval(live_sell())
        self.assertTrue(ok, reason)

    def test_hook_payload_shape_allowed(self):
        ok, reason = self._eval({"tool_name": "mcp__robinhood-trading__place_equity_order",
                                 "tool_input": live_buy()})
        self.assertTrue(ok, reason)

    def test_extended_and_all_day_hours_denied(self):
        for hours in ("extended_hours", "all_day_hours"):
            ok, _ = self._eval(live_buy(market_hours=hours))
            self.assertFalse(ok, hours)

    def test_missing_or_bad_side_denied(self):
        order = live_buy()
        del order["side"]
        self.assertFalse(self._eval(order)[0])
        self.assertFalse(self._eval(live_buy(side="short"))[0])

    def test_wrong_or_missing_account_denied(self):
        self.assertFalse(self._eval(live_buy(account_number="OTHER"))[0])
        self.assertFalse(self._eval(live_buy(), account=None)[0])

    def test_cancel_tool_denied(self):
        ok, reason = self._eval({"tool_name": "mcp__robinhood-trading__cancel_equity_order",
                                 "tool_input": {"account_number": AGENT, "order_id": "x"}})
        self.assertFalse(ok)
        self.assertIn("cancel", reason)

    def test_sell_needs_quantity(self):
        order = live_sell()
        del order["quantity"]
        self.assertFalse(self._eval(order)[0])
        self.assertFalse(self._eval(live_sell(dollar_amount=50))[0])

    def test_buy_quantity_or_nonpositive_denied(self):
        self.assertFalse(self._eval(live_buy(quantity=1))[0])
        self.assertFalse(self._eval(live_buy(dollar_amount=0))[0])

    def test_limit_denied(self):
        ok, _ = order_guard.evaluate(
            {"side": "buy", "symbol": "AAPL", "type": "limit", "dollar_amount": 100,
             "time_in_force": "gfd"},
            rules_live(), set(), set(), now_et=weekday_1030_et(),
        )
        self.assertFalse(ok)

    def test_outside_window_denied(self):
        late = datetime(2026, 10, 21, 14, 0, tzinfo=ZoneInfo("America/New_York"))
        ok, _ = order_guard.evaluate(
            {"side": "buy", "symbol": "AAPL", "type": "market", "dollar_amount": 100,
             "time_in_force": "gfd"},
            rules_live(), set(), set(), now_et=late,
        )
        self.assertFalse(ok)

    def test_holiday_denied(self):
        ok, _ = order_guard.evaluate(
            {"side": "buy", "symbol": "AAPL", "type": "market", "dollar_amount": 100,
             "time_in_force": "gfd"},
            rules_live(), set(), {"2026-10-21"}, now_et=weekday_1030_et(),
        )
        self.assertFalse(ok)

    def test_over_max_order_denied(self):
        ok, _ = order_guard.evaluate(
            {"side": "buy", "symbol": "AAPL", "type": "market", "dollar_amount": 501,
             "time_in_force": "gfd"},
            rules_live(), set(), set(), now_et=weekday_1030_et(),
        )
        self.assertFalse(ok)

    def test_excluded_symbol_denied(self):
        ok, _ = order_guard.evaluate(
            {"side": "buy", "symbol": "TQQQ", "type": "market", "dollar_amount": 50,
             "time_in_force": "gfd"},
            rules_live(), {"TQQQ"}, set(), now_et=weekday_1030_et(),
        )
        self.assertFalse(ok)

    def test_option_denied(self):
        ok, _ = order_guard.evaluate(
            {"side": "buy", "symbol": "AAPL", "type": "market", "dollar_amount": 50,
             "time_in_force": "gfd", "asset_type": "option"},
            rules_live(), set(), set(), now_et=weekday_1030_et(),
        )
        self.assertFalse(ok)

    def test_buy_missing_dollar_amount(self):
        ok, _ = order_guard.evaluate(
            {"side": "buy", "symbol": "AAPL", "type": "market", "quantity": 1,
             "time_in_force": "gfd"},
            rules_live(), set(), set(), now_et=weekday_1030_et(),
        )
        self.assertFalse(ok)

    def test_malformed_stdin_denies(self):
        proc = subprocess.run(
            [sys.executable, str(GUARD)],
            input="not-json",
            text=True,
            capture_output=True,
            cwd=str(ROOT),
            env={**dict(**{k: v for k, v in __import__("os").environ.items()}),
                 "CLAUDE_PROJECT_DIR": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 2)

    def test_empty_stdin_denies(self):
        proc = subprocess.run(
            [sys.executable, str(GUARD)],
            input="",
            text=True,
            capture_output=True,
            env={"CLAUDE_PROJECT_DIR": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
