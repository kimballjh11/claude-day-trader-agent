#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pnl_pct


class TestPnlPct(unittest.TestCase):
    def test_equity_history_drawdown_halts(self):
        hist = [
            {"date": "2026-11-02", "equity_usd": 1000.0},
            {"date": "2026-11-03", "equity_usd": 950.0},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(hist, f)
            path = f.name
        # 5% daily drop vs 4% limit → halt
        import subprocess

        out = subprocess.check_output(
            [
                sys.executable,
                str(ROOT / "scripts" / "pnl_pct.py"),
                "--equity-history",
                path,
                "--as-of",
                "2026-11-03",
                "--net-deposits-usd",
                "1000",
                "--daily-limit-pct",
                "0.04",
                "--weekly-limit-pct",
                "0.08",
            ],
            text=True,
        )
        data = json.loads(out)
        self.assertTrue(data["entries_halted"])
        self.assertAlmostEqual(data["daily_pnl_pct"], -0.05, places=5)

    def test_drawdown_helper(self):
        stats = pnl_pct.drawdown_from_history(
            [
                {"date": "2026-11-02", "equity_usd": 1000.0},
                {"date": "2026-11-03", "equity_usd": 1000.0},
            ],
            as_of="2026-11-03",
            net_deposits_usd=1000.0,
        )
        self.assertEqual(stats["daily_pnl_pct"], 0.0)


class TestPnlPctBases(unittest.TestCase):
    def test_weekly_base_is_last_week_so_monday_counts(self):
        hist = [
            {"date": "2026-10-30", "equity_usd": 1000.0},  # Friday
            {"date": "2026-11-02", "equity_usd": 910.0},   # Monday's mark
        ]
        stats = pnl_pct.drawdown_from_history(hist, as_of="2026-11-02", net_deposits_usd=1000.0)
        self.assertAlmostEqual(stats["daily_pnl_pct"], -0.09)
        self.assertAlmostEqual(stats["weekly_pnl_pct"], -0.09)

    def test_without_todays_mark_daily_is_zero(self):
        # Documents why Phase B must mark the books (B3) before B4.
        hist = [{"date": "2026-11-02", "equity_usd": 1000.0}]
        stats = pnl_pct.drawdown_from_history(hist, as_of="2026-11-03", net_deposits_usd=1000.0)
        self.assertEqual(stats["daily_pnl_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
