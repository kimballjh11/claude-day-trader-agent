#!/usr/bin/env python3
import json, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "position_sizing.py"

def run(cands, overrides=None):
    cmd = [sys.executable, str(SCRIPT),
        "--total-value","1000","--cash-start","1000","--concurrent-positions-start","0",
        "--max-position-pct","0.15","--max-concurrent-positions","5","--min-cash-buffer-pct","0.15",
        "--min-top-up-usd","5","--min-top-up-pct-of-target","0.10",
        "--conviction-pct","high:0.15,medium:0.10,low:0.05",
        "--max-order-usd","500","--max-new-per-session","2","--max-per-sector","3","--min-order-usd","5"]
    if overrides: cmd.extend(overrides)
    proc = subprocess.run(cmd, input=json.dumps(cands), text=True, capture_output=True, cwd=str(ROOT))
    if proc.returncode != 0: raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)

class TestPositionSizing(unittest.TestCase):
    def test_tiers_at_1000(self):
        for conv, exp in [("high",150.0),("medium",100.0),("low",50.0)]:
            out = run([{"symbol":"AAA","group":"new","conviction":conv,"sector":"Tech"}])
            self.assertTrue(out["results"][0]["passed"])
            self.assertEqual(out["results"][0]["dollar_amount"], exp)

    def test_max_order_cap(self):
        out = run([{"symbol":"AAA","group":"new","conviction":"high","sector":"Tech"}],
                  ["--total-value","10000","--cash-start","10000"])
        self.assertEqual(out["results"][0]["dollar_amount"], 500.0)

    def test_cash_floor(self):
        out = run([{"symbol":"AAA","group":"new","conviction":"high","sector":"Tech"}],
                  ["--cash-start","160"])
        self.assertTrue(out["results"][0]["passed"])
        self.assertEqual(out["results"][0]["dollar_amount"], 10.0)
        self.assertEqual(out["results"][0]["cash_remaining_after"], 150.0)

    def test_rounds_down_at_cash_floor(self):
        # Rounding to nearest cent used to give $10.01 and breach the $150.45 floor.
        out = run([{"symbol":"AAA","group":"new","conviction":"high","sector":"Tech"}],
                  ["--total-value","1003","--cash-start","160.455"])
        self.assertTrue(out["results"][0]["passed"], out["results"][0].get("reason"))
        self.assertEqual(out["results"][0]["dollar_amount"], 10.0)

    def test_max_five_positions(self):
        cands = [{"symbol":f"S{i}","group":"new","conviction":"low","sector":f"Sec{i}"} for i in range(6)]
        out = run(cands, ["--max-new-per-session","10"])
        self.assertEqual(sum(1 for r in out["results"] if r["passed"]), 5)

    def test_max_two_new_per_session(self):
        cands = [{"symbol":s,"group":"new","conviction":"low","sector":s} for s in "ABC"]
        out = run(cands)
        self.assertTrue(out["results"][0]["passed"] and out["results"][1]["passed"])
        self.assertFalse(out["results"][2]["passed"])

    def test_min_order(self):
        out = run([{"symbol":"AAA","group":"new","conviction":"low","sector":"Tech"}],
                  ["--cash-start","154"])
        self.assertFalse(out["results"][0]["passed"])

if __name__ == "__main__":
    unittest.main()
