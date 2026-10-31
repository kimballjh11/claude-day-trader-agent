#!/usr/bin/env python3
"""Tests for scripts/paper_broker.py."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "paper_broker.py"


class TestPaperBroker(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.paper = self.tmp / "paper"
        self.paper.mkdir()
        # Point broker at temp by monkeypatching via cwd copy of minimal tree
        self.work = self.tmp / "work"
        self.work.mkdir()
        (self.work / "paper").mkdir()
        (self.work / "data").mkdir()
        (self.work / "data" / "universe").mkdir(parents=True)
        shutil.copy(ROOT / "data" / "market_holidays.json", self.work / "data" / "market_holidays.json")
        # Run by importing with PAPER_DIR override via env — use subprocess with
        # a patched copy of the script directory approach: call module functions.
        sys.path.insert(0, str(ROOT / "scripts"))
        import paper_broker as pb

        self.pb = pb
        self._orig_root = pb.ROOT
        self._orig_paper = pb.PAPER_DIR
        pb.ROOT = self.work
        pb.PAPER_DIR = self.work / "paper"

    def tearDown(self):
        self.pb.ROOT = self._orig_root
        self.pb.PAPER_DIR = self._orig_paper
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_buy_sell_settle_weekend_holiday(self):
        pb = self.pb
        pb.cmd_init("claude", 1000.0, "2026-11-02")
        pb.cmd_fill_buy("claude", "AAA", 100.0, 10.0, "2026-11-02", sector="Tech")
        ledger = pb._load("claude")
        self.assertEqual(len(ledger["positions"]), 1)
        self.assertAlmostEqual(ledger["cash_settled_usd"], 900.0)

        # Sell Friday; settlement skips weekend → Monday
        pb.cmd_fill_sell("claude", "AAA", 5.0, 12.0, "2026-11-06", "take_profit")
        ledger = pb._load("claude")
        self.assertEqual(ledger["cash_unsettled"][0]["settles_on"], "2026-11-09")

        pb.cmd_settle("claude", "2026-11-09")
        ledger = pb._load("claude")
        self.assertEqual(ledger["cash_unsettled"], [])
        self.assertAlmostEqual(ledger["cash_settled_usd"], 960.0)  # 900 + 60

    def test_refuse_insufficient_cash(self):
        pb = self.pb
        pb.cmd_init("claude", 1000.0, "2026-11-02")
        with self.assertRaises(ValueError):
            pb.cmd_fill_buy(
                "claude", "AAA", 900.0, 10.0, "2026-11-02", min_cash_buffer_pct=0.15
            )

    def test_mark_to_market(self):
        pb = self.pb
        pb.cmd_init("control", 1000.0, "2026-11-02")
        pb.cmd_fill_buy("control", "BBB", 100.0, 20.0, "2026-11-02")
        pb.cmd_mark("control", {"BBB": 22.0}, "2026-11-03", "morning")
        ledger = pb._load("control")
        self.assertEqual(ledger["positions"][0]["last_price_usd"], 22.0)
        self.assertEqual(ledger["equity_history"][-1]["equity_usd"], pb._equity(ledger))

    def test_atomic_refuse_overwrite_init(self):
        pb = self.pb
        pb.cmd_init("claude", 1000.0, "2026-11-02")
        with self.assertRaises(FileExistsError):
            pb.cmd_init("claude", 1000.0, "2026-11-02")

    def test_partial_sell_logs_and_tp_tier(self):
        pb = self.pb
        pb.cmd_init("claude", 1000.0, "2026-11-02")
        pb.cmd_fill_buy("claude", "AAA", 100.0, 10.0, "2026-11-02")
        pb.cmd_fill_sell(
            "claude", "AAA", 2.5, 12.0, "2026-11-03", "take_profit", take_profit_tier=0.15
        )
        ledger = pb._load("claude")
        self.assertEqual(len(ledger["closed_trades"]), 1)
        self.assertTrue(ledger["closed_trades"][0]["partial"])
        self.assertEqual(ledger["closed_trades"][0]["take_profit_tier"], 0.15)
        self.assertIn(0.15, ledger["positions"][0]["take_profit_tiers_hit"])
        self.assertAlmostEqual(ledger["positions"][0]["quantity"], 7.5)

    def test_benchmark_indexes_to_1000(self):
        pb = self.pb
        bench = pb.cmd_benchmark(500.0, "2026-11-02", "init", inception_spy=500.0)
        self.assertEqual(bench["indexed_equity_usd"], 1000.0)
        bench = pb.cmd_benchmark(550.0, "2026-11-03", "morning")
        self.assertEqual(bench["indexed_equity_usd"], 1100.0)


if __name__ == "__main__":
    unittest.main()
