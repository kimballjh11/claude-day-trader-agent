#!/usr/bin/env python3
"""Tests for scripts/build_dashboard_data.py schema."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_dashboard_data as bdd  # noqa: E402

REQUIRED_TOP = {
    "generated_at",
    "mode",
    "phase",
    "last_run",
    "next_runs",
    "errors",
    "books",
    "equity_series",
    "positions",
    "sector_exposure",
    "decisions_today",
    "blocked",
    "recent_trades",
    "graduation",
    "signal_attribution",
    "unvoted_count",
}


class TestBuildDashboardData(unittest.TestCase):
    def test_schema_and_empty_ok(self):
        state = bdd.build_state()
        self.assertTrue(REQUIRED_TOP.issubset(state.keys()))
        self.assertIn("claude", state["books"])
        self.assertIn("control", state["books"])
        self.assertIn("spy", state["books"])
        for key in (
            "equity_series",
            "positions",
            "decisions_today",
            "blocked",
            "recent_trades",
            "signal_attribution",
            "errors",
        ):
            self.assertIsInstance(state[key], list)
        self.assertIsInstance(state["sector_exposure"], dict)
        self.assertIn("items", state["graduation"])

    def test_last_evening_decisions_stay_votable(self):
        decisions = [
            {"decision_id": "20261020-OLD-claude", "symbol": "OLD"},
            {"decision_id": "20261021-AAA-claude", "symbol": "AAA"},
            {"decision_id": "20261022-BBB-claude", "symbol": "BBB"},
            {"decision_id": "20261022-BBB-control", "symbol": "BBB"},
        ]
        votes = {"20261020-OLD-claude": "agree"}
        cards, votable = bdd._decision_panel(decisions, votes)
        ids = [c["decision_id"] for c in cards]
        self.assertIn("20261021-AAA-claude", ids)  # last evening still shown
        self.assertIn("20261022-BBB-claude", ids)
        self.assertNotIn("20261020-OLD-claude", ids)  # old and already voted
        self.assertEqual(
            votable, ["20261020-OLD-claude", "20261021-AAA-claude", "20261022-BBB-claude"]
        )

    def test_old_unvoted_decision_still_shown(self):
        decisions = [
            {"decision_id": "20261019-OLD-claude"},
            {"decision_id": "20261021-AAA-claude"},
            {"decision_id": "20261022-BBB-claude"},
        ]
        cards, _ = bdd._decision_panel(decisions, {})
        self.assertIn("20261019-OLD-claude", [c["decision_id"] for c in cards])

    def test_scheduled_runs_skip_weekend_and_holiday(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        schedule = {
            "timezone": "America/Denver",
            "phase_a_local_time": "15:30",
            "phase_b_local_time": "08:00",
            "weekly_review_local_time": "16:30",
        }
        now = datetime(2026, 11, 25, 16, 0, tzinfo=ZoneInfo("America/Denver"))  # Wed after evening slot
        runs = bdd._scheduled_runs(schedule, {"2026-11-26"}, now=now, days=5)
        labels = [(r["run"], r["scheduled_at"][:16]) for r in runs]
        self.assertEqual(
            labels[:4],
            [
                ("morning", "2026-11-27T08:00"),
                ("evening", "2026-11-27T15:30"),
                ("weekly", "2026-11-27T16:30"),
                ("morning", "2026-11-30T08:00"),
            ],
        )

    def test_next_take_profit_uses_rule_tiers(self):
        pos = {"avg_cost_usd": 100, "take_profit_tiers_hit": [0.15]}
        self.assertEqual(bdd._next_take_profit(pos, [0.5, 0.15, 0.3]), 130.0)
        self.assertIsNone(bdd._next_take_profit({"avg_cost_usd": 100, "take_profit_tiers_hit": [0.15, 0.3, 0.5]}, [0.15, 0.3, 0.5]))

    def test_writes_file_to_temp_not_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "state.json"
            with mock.patch.object(bdd, "OUT", out):
                self.assertEqual(bdd.main(), 0)
            self.assertTrue(out.exists())
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["mode"], "paper")


if __name__ == "__main__":
    unittest.main()
