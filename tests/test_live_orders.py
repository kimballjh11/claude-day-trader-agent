#!/usr/bin/env python3
"""Tests for scripts/live_orders.py and live book mapping."""
import json
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import book  # noqa: E402
import live_orders  # noqa: E402


def paper_rules():
    return json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))


def live_rules():
    r = deepcopy(paper_rules())
    r["execution"]["mode"] = "live"
    r["autonomy"]["phase"] = 2
    return r


@mock.patch.dict(os.environ, {"RH_AGENT_ACCOUNT_NUMBER": "TESTACCT1"})
class TestLiveOrders(unittest.TestCase):
    def test_build_buy_denied_in_paper(self):
        with self.assertRaises(live_orders.LiveTradingDisabled):
            live_orders.build_market_buy(symbol="AAPL", dollar_amount=50, rules=paper_rules())

    def test_build_buy_ok_in_live(self):
        payload = live_orders.build_market_buy(
            symbol="AAPL", dollar_amount=50, rules=live_rules()
        )
        self.assertEqual(payload["type"], "market")
        self.assertEqual(payload["side"], "buy")
        self.assertEqual(payload["dollar_amount"], "50.00")
        self.assertEqual(payload["time_in_force"], "gfd")

    def test_over_max_order(self):
        with self.assertRaises(ValueError):
            live_orders.build_market_buy(symbol="AAPL", dollar_amount=501, rules=live_rules())

    def test_classify_held(self):
        c = live_orders.classify_order_status(
            {"status": "pending_approval", "message": "Waiting for your approval"}
        )
        self.assertEqual(c["code"], "ROBINHOOD_APPROVAL_REQUIRED")

    def test_confirm_unconfirmed_after_two_polls(self):
        polls = [{"status": "pending"}, {"status": "pending"}]
        out = live_orders.confirm_after_polls(polls)
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "ORDER_NOT_CONFIRMED")

    def test_confirm_filled(self):
        out = live_orders.confirm_after_polls([{"status": "submitted"}, {"status": "filled"}])
        self.assertTrue(out["ok"])

    def test_build_payload_fields(self):
        buy = live_orders.build_market_buy(symbol="aapl", dollar_amount=50, rules=live_rules())
        sell = live_orders.build_market_sell(symbol="AAPL", quantity=1.5, rules=live_rules())
        for payload in (buy, sell):
            self.assertEqual(payload["account_number"], "TESTACCT1")
            self.assertEqual(payload["market_hours"], "regular_hours")
            self.assertTrue(payload["ref_id"])
        self.assertNotEqual(buy["ref_id"], sell["ref_id"])

    def test_payload_strings_and_rounding(self):
        buy = live_orders.build_market_buy(symbol="AAPL", dollar_amount=10.019, rules=live_rules())
        self.assertEqual(buy["dollar_amount"], "10.01")
        sell = live_orders.build_market_sell(symbol="AAPL", quantity=0.12345678, rules=live_rules())
        self.assertEqual(sell["quantity"], "0.123456")
        self.assertEqual(live_orders.build_market_sell(symbol="AAPL", quantity=2, rules=live_rules())["quantity"], "2")
        self.assertNotIn("ref_id", live_orders.for_review(buy))
        self.assertIn("ref_id", buy)

    def test_build_requires_account_env(self):
        with mock.patch.dict(os.environ, {"RH_AGENT_ACCOUNT_NUMBER": ""}):
            with self.assertRaises(ValueError):
                live_orders.build_market_buy(symbol="AAPL", dollar_amount=50, rules=live_rules())

    def test_orders_match_log_missing(self):
        v = live_orders.orders_match_log(
            placed=[{"symbol": "AAA", "side": "buy", "order_id": "o1", "book": "claude"}],
            broker_orders=[{"id": "o2", "symbol": "AAA", "side": "buy"}],
        )
        self.assertEqual([x["code"] for x in v], ["LIVE_ORDER_MISSING"])

    def test_orders_match_log_by_id(self):
        v = live_orders.orders_match_log(
            placed=[{"symbol": "AAA", "side": "buy", "order_id": "o1"}],
            broker_orders=[{"id": "o1", "symbol": "AAA", "side": "buy"}],
        )
        self.assertEqual(v, [])

    def test_orders_match_log_no_id_and_mismatch(self):
        v = live_orders.orders_match_log(
            placed=[
                {"symbol": "AAA", "side": "buy"},
                {"symbol": "AAA", "side": "buy", "order_id": "o1"},
            ],
            broker_orders=[{"id": "o1", "symbol": "BBB", "side": "buy"}],
        )
        self.assertEqual([x["code"] for x in v], ["LIVE_ORDER_NO_ID", "LIVE_ORDER_MISMATCH"])

    def test_map_live_verified_fields(self):
        normalized = book.map_live_mcp_to_ledger(
            portfolio={"cash": "900.00", "buying_power": {"buying_power": "5000"}},
            account={"unsettled_funds": "100.00"},
            positions=[],
        )
        self.assertEqual(normalized["cash_settled_usd"], 800.0)
        self.assertEqual(normalized["cash_unsettled_usd"], 100.0)

    def test_map_live_refuses_buying_power_fallback(self):
        with self.assertRaises(ValueError):
            book.map_live_mcp_to_ledger(
                portfolio={"buying_power": {"buying_power": "5000"}},
                account={"unsettled_funds": "0"},
                positions=[],
            )
        with self.assertRaises(ValueError):
            book.map_live_mcp_to_ledger(portfolio={"cash": "900"}, positions=[])

    def test_map_live_mcp(self):
        normalized = book.map_live_mcp_to_ledger(
            portfolio={"settled_cash": 800.0, "unsettled_cash": 50.0},
            positions=[
                {
                    "symbol": "AAPL",
                    "quantity": 1.5,
                    "average_buy_price": 100.0,
                    "last_trade_price": 110.0,
                    "sector": "Technology",
                }
            ],
        )
        self.assertEqual(normalized["mode"], "live")
        self.assertEqual(normalized["cash_settled_usd"], 800.0)
        self.assertEqual(normalized["cash_unsettled_usd"], 50.0)
        self.assertEqual(len(normalized["positions"]), 1)
        self.assertEqual(normalized["positions"][0]["market_value_usd"], 165.0)

    def test_control_always_paper_even_if_mode_live(self):
        # load_book for control ignores live mode when file exists
        out = book.load_book("control", mode="live")
        self.assertEqual(out["mode"], "paper")
        self.assertEqual(out["book"], "control")


if __name__ == "__main__":
    unittest.main()
