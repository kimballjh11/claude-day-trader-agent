#!/usr/bin/env python3
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import control_book  # noqa: E402


def rules():
    return json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))


class TestControlBook(unittest.TestCase):
    def test_every_candidate_medium(self):
        researched = [
            {"symbol": "AAA", "is_holding": False, "asset_type": "stock", "mom_12_1": 0.2},
            {"symbol": "BBB", "is_holding": True, "asset_type": "stock", "mom_12_1": 0.1},
            {"symbol": "SPY", "is_holding": False, "asset_type": "etf", "mom_12_1": 0.05},
        ]
        out = control_book.build_control_proposals(researched, rules(), as_of="2026-11-03")
        buys = [p for p in out if p["action"] == "buy"]
        holds = [p for p in out if p["action"] == "hold"]
        self.assertEqual(len(buys), 2)
        self.assertEqual(len(holds), 1)
        for p in buys:
            self.assertEqual(p["conviction"], "medium")
            self.assertTrue(p["proposal_id"].endswith("-control"))
        self.assertFalse(any(p.get("thesis_exits") for p in out))

    def test_etf_stays_medium(self):
        researched = [{"symbol": "QQQ", "is_holding": False, "asset_type": "etf", "mom_12_1": 0.1}]
        out = control_book.build_control_proposals(researched, rules(), as_of="2026-11-03")
        self.assertEqual(out[0]["conviction"], "medium")


if __name__ == "__main__":
    unittest.main()
