#!/usr/bin/env python3
import json, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rank_candidates.py"

def rank(cands):
    proc = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(cands), text=True, capture_output=True, cwd=str(ROOT))
    if proc.returncode != 0: raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)

class TestRank(unittest.TestCase):
    def test_conviction_then_mom_then_flags(self):
        cands = [
            {"symbol":"LOW_HIGH_MOM","conviction":"low","mom_12_1":0.9,"risk_flags":[]},
            {"symbol":"HIGH_LOW_MOM","conviction":"high","mom_12_1":0.1,"risk_flags":["a"]},
            {"symbol":"HIGH_HIGH_MOM","conviction":"high","mom_12_1":0.5,"risk_flags":["a","b"]},
            {"symbol":"HIGH_HIGH_MOM_FEWER_FLAGS","conviction":"high","mom_12_1":0.5,"risk_flags":[]},
            {"symbol":"MED","conviction":"medium","mom_12_1":0.99,"risk_flags":[]},
        ]
        symbols = [c["symbol"] for c in rank(cands)]
        self.assertEqual(symbols, [
            "HIGH_HIGH_MOM_FEWER_FLAGS","HIGH_HIGH_MOM","HIGH_LOW_MOM","MED","LOW_HIGH_MOM"])

if __name__ == "__main__":
    unittest.main()
