#!/usr/bin/env python3
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit  # noqa: E402


def rules():
    return json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))


class TestAudit(unittest.TestCase):
    def test_max_order_detected(self):
        v = audit.audit_session(
            rules=rules(),
            fills=[{"book": "claude", "symbol": "AAA", "side": "buy", "amount_usd": 600}],
            ledgers={"claude": {"cash_settled_usd": 1000, "cash_unsettled": [], "positions": []}},
        )
        self.assertTrue(any(x["code"] == "MAX_ORDER" for x in v))

    def test_real_order_in_paper(self):
        v = audit.audit_session(
            rules=rules(),
            fills=[{"book": "claude", "symbol": "AAA", "placed_real_order": True}],
            ledgers={"claude": {"cash_settled_usd": 1000, "cash_unsettled": [], "positions": []}},
        )
        self.assertTrue(any(x["code"] == "REAL_ORDER_IN_PAPER" for x in v))

    def test_max_positions(self):
        positions = [
            {"symbol": f"S{i}", "sector": f"Sec{i}", "quantity": 1, "avg_cost_usd": 10, "last_price_usd": 10}
            for i in range(6)
        ]
        v = audit.audit_session(
            rules=rules(),
            fills=[],
            ledgers={"claude": {"cash_settled_usd": 100, "cash_unsettled": [], "positions": positions}},
        )
        self.assertTrue(any(x["code"] == "MAX_POSITIONS" for x in v))

    def test_sector_cap(self):
        positions = [
            {"symbol": f"S{i}", "sector": "Technology", "quantity": 1, "avg_cost_usd": 10, "last_price_usd": 10}
            for i in range(4)
        ]
        v = audit.audit_session(
            rules=rules(),
            fills=[],
            ledgers={"claude": {"cash_settled_usd": 100, "cash_unsettled": [], "positions": positions}},
        )
        self.assertTrue(any(x["code"] == "SECTOR_CAP" for x in v))

    def test_buy_during_halt(self):
        v = audit.audit_session(
            rules=rules(),
            fills=[{"book": "claude", "symbol": "AAA", "side": "buy", "halted": True, "amount_usd": 50}],
            ledgers={"claude": {"cash_settled_usd": 1000, "cash_unsettled": [], "positions": []}},
        )
        self.assertTrue(any(x["code"] == "BUY_DURING_HALT" for x in v))

    def test_excluded_symbol(self):
        v = audit.audit_session(
            rules=rules(),
            fills=[{"book": "claude", "symbol": "TQQQ", "excluded_symbol": True, "amount_usd": 50}],
            ledgers={"claude": {"cash_settled_usd": 1000, "cash_unsettled": [], "positions": []}},
        )
        self.assertTrue(any(x["code"] == "EXCLUDED_SYMBOL" for x in v))

    def test_reconcile_equity_vs_last_mark(self):
        ledger = {
            "cash_settled_usd": 900,
            "cash_unsettled": [{"amount_usd": 50, "settles_on": "2026-10-23"}],
            "positions": [{"symbol": "AAA", "quantity": 1, "avg_cost_usd": 100, "last_price_usd": 110}],
            "equity_history": [{"date": "2026-10-22", "run": "morning", "equity_usd": 1060.0}],
        }
        self.assertIsNone(audit.reconcile_ledger(ledger))
        ledger["equity_history"][-1]["equity_usd"] = 1000.0
        self.assertTrue(audit.reconcile_ledger(ledger).startswith("equity_mismatch"))

    def test_reconcile_bad_unsettled(self):
        ledger = {"cash_settled_usd": 0, "cash_unsettled": [{"amount_usd": 5}], "positions": []}
        self.assertEqual(audit.reconcile_ledger(ledger), "bad_unsettled_entry")

    def test_clean_session(self):
        v = audit.audit_session(
            rules=rules(),
            fills=[{"book": "claude", "symbol": "AAA", "side": "buy", "amount_usd": 100, "is_new_position": True}],
            ledgers={
                "claude": {
                    "cash_settled_usd": 900,
                    "cash_unsettled": [],
                    "positions": [
                        {
                            "symbol": "AAA",
                            "sector": "Tech",
                            "quantity": 1,
                            "avg_cost_usd": 100,
                            "last_price_usd": 100,
                        }
                    ],
                }
            },
        )
        self.assertEqual(v, [])


if __name__ == "__main__":
    unittest.main()
