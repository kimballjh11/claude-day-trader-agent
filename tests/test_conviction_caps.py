#!/usr/bin/env python3
import json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import conviction_caps

def rules():
    return json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))

class TestConvictionCaps(unittest.TestCase):
    def test_jsonl_in_place(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending_proposals.jsonl"
            path.write_text(
                json.dumps({"symbol": "QQQ", "action": "buy", "conviction": "high", "asset_type": "etf"}) + "\n"
                + json.dumps({"symbol": "AAPL", "action": "buy", "conviction": "high", "asset_type": "stock"}) + "\n",
                encoding="utf-8",
            )
            rc = conviction_caps.main(["--rules", str(ROOT / "risk_rules.json"),
                                       "--proposals", str(path), "--write-jsonl", str(path)])
            self.assertEqual(rc, 0)
            rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["conviction"] for r in rows], ["medium", "high"])

    def test_etf_capped_at_medium(self):
        out = conviction_caps.apply_caps(conviction="high", asset_type="etf",
            macro_regime="Expansion", ahead_of_earnings=False, rules=rules())
        self.assertEqual(out["conviction_out"], "medium")

    def test_regime_caps(self):
        for regime in ("Contraction", "Inflationary"):
            out = conviction_caps.apply_caps(conviction="high", asset_type="stock",
                macro_regime=regime, ahead_of_earnings=False, rules=rules())
            self.assertEqual(out["conviction_out"], "medium")

    def test_earnings_cap(self):
        out = conviction_caps.apply_caps(conviction="high", asset_type="stock",
            macro_regime=None, ahead_of_earnings=True, rules=rules())
        self.assertEqual(out["conviction_out"], "medium")

    def test_never_raises(self):
        out = conviction_caps.apply_caps(conviction="low", asset_type="stock",
            macro_regime="Expansion", ahead_of_earnings=False, rules=rules())
        self.assertEqual(out["conviction_out"], "low")

if __name__ == "__main__":
    unittest.main()
