#!/usr/bin/env python3
import json, sys, unittest
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import momentum

def rules():
    return json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))

def make_bars(n, start=100.0, daily_ret=0.001, volume=1_000_000):
    bars, price, d0 = [], start, date(2024, 1, 2)
    for i in range(n):
        d = d0 + timedelta(days=i)
        bars.append({"date": d.isoformat(), "close": round(price, 6), "high": round(price*1.01, 6), "volume": volume})
        price *= 1.0 + daily_ret
    return bars

class TestMomentum(unittest.TestCase):
    def test_mom_12_1_known(self):
        d0 = date(2023, 1, 1)
        bars = [{"date": (d0 + timedelta(days=i)).isoformat(), "close": 100.0, "high": 100.0, "volume": 1e6} for i in range(253)]
        bars[0]["close"] = 100.0
        bars[231]["close"] = 120.0
        bars[252]["close"] = 130.0
        self.assertAlmostEqual(momentum.mom_12_1(bars), 0.2)

    def test_under_253_bars_null(self):
        self.assertIsNone(momentum.mom_12_1(make_bars(252)))

    def test_ret_60d(self):
        d0 = date(2024, 1, 1)
        bars = [{"date": (d0 + timedelta(days=i)).isoformat(), "close": 100.0 + i, "high": 100.0 + i, "volume": 1e6} for i in range(70)]
        self.assertAlmostEqual(momentum.ret_60d(bars), 169.0 / 109.0 - 1.0)

    def test_vol_ratio(self):
        bars = make_bars(40)
        bars[-1]["volume"] = 2_500_000
        self.assertAlmostEqual(momentum.vol_ratio(bars), 2.5)

    def test_pct_from_52wk_high(self):
        bars = make_bars(260)
        for b in bars: b["high"] = b["close"]
        bars[-10]["high"] = 200.0
        bars[-1]["close"] = 194.0
        self.assertAlmostEqual(momentum.pct_from_52wk_high(bars), (200.0 - 194.0) / 200.0)

    def test_gate_each_trigger(self):
        r = rules()
        base = {"mom_12_1": 0.1, "ret_60d": 0.0, "vol_ratio": 1.0, "pct_from_52wk_high": 0.5}
        bars = make_bars(30); bars[-1]["close"] = 101; bars[-2]["close"] = 100
        self.assertIn("ret_60d", momentum.signal_gate({**base, "ret_60d": 0.10}, bars, r)["signals_fired"])
        self.assertIn("vol_ratio", momentum.signal_gate({**base, "vol_ratio": 2.0}, bars, r)["signals_fired"])
        self.assertIn("near_52wk_high", momentum.signal_gate({**base, "pct_from_52wk_high": 0.03}, bars, r)["signals_fired"])
        self.assertFalse(momentum.signal_gate({**base, "mom_12_1": -0.01, "ret_60d": 0.5}, bars, r)["passed"])
        self.assertEqual(momentum.signal_gate(base, bars, r, is_holding=True)["signals_fired"], ["holding_exempt"])

if __name__ == "__main__":
    unittest.main()
