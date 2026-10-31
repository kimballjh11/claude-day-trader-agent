#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import entry_gate


class TestEntryGateReasons(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(entry_gate.normalize_sell_reason("trim"), "conviction_trim")
        self.assertEqual(entry_gate.normalize_sell_reason("thesis_exit"), "exit_existing")
        self.assertEqual(entry_gate.normalize_sell_reason("stop_loss"), "stop_loss")


if __name__ == "__main__":
    unittest.main()
