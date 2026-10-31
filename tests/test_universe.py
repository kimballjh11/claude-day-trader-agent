#!/usr/bin/env python3
import json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import universe

def rules():
    return json.loads((ROOT / "risk_rules.json").read_text(encoding="utf-8"))

class TestUniverse(unittest.TestCase):
    def test_sp500_any_size_passes(self):
        r = universe.evaluate_symbol(symbol="AAPL", asset_type="stock", rules=rules(),
            sp500={"AAPL": "Technology"}, etf_exclusions=[], price=180.0,
            avg_daily_volume=50_000_000, market_cap_usd=100_000_000, close=180.0, sma_200=170.0)
        self.assertTrue(r["eligible"], r)

    def test_non_member_below_2b_fails(self):
        r = universe.evaluate_symbol(symbol="SMALL", asset_type="stock", rules=rules(),
            sp500={}, etf_exclusions=[], price=20.0, avg_daily_volume=2_000_000,
            market_cap_usd=1_900_000_000, close=20.0, sma_200=18.0)
        self.assertFalse(r["eligible"])

    def test_non_member_above_50b_fails(self):
        r = universe.evaluate_symbol(symbol="HUGE", asset_type="stock", rules=rules(),
            sp500={}, etf_exclusions=[], price=20.0, avg_daily_volume=2_000_000,
            market_cap_usd=51_000_000_000, close=20.0, sma_200=18.0)
        self.assertFalse(r["eligible"])

    def test_midcap_band_passes(self):
        r = universe.evaluate_symbol(symbol="MID", asset_type="stock", rules=rules(),
            sp500={}, etf_exclusions=[], price=20.0, avg_daily_volume=2_000_000,
            market_cap_usd=10_000_000_000, close=20.0, sma_200=18.0)
        self.assertTrue(r["eligible"], r)

    def test_leveraged_etf_excluded(self):
        ex, _ = universe.is_excluded_product("TQQQ", name="ProShares UltraPro QQQ", asset_type="etf", rules=rules())
        self.assertTrue(ex)

    def test_inverse_etf_excluded(self):
        ex, _ = universe.is_excluded_product("SH", name="ProShares Short S&P500", asset_type="etf", rules=rules())
        self.assertTrue(ex)

    def test_vix_product_excluded(self):
        ex, _ = universe.is_excluded_product("VXX", name="iPath Series B S&P 500 VIX", asset_type="etf", rules=rules())
        self.assertTrue(ex)

    def test_crypto_etf_excluded_by_keyword(self):
        ex, reason = universe.is_excluded_product(
            "ETHA", name="iShares Ethereum Trust ETF", asset_type="etf", rules=rules()
        )
        self.assertTrue(ex)
        self.assertEqual(reason, "crypto_product_keyword")

    def test_crypto_etf_excluded_by_list(self):
        ex, reason = universe.is_excluded_product(
            "IBIT", etf_exclusions=["IBIT"], asset_type="etf", rules=rules()
        )
        self.assertTrue(ex)
        self.assertEqual(reason, "listed_in_etf_exclusions")

    def test_listed_exclusion(self):
        ex, reason = universe.is_excluded_product("UVXY", etf_exclusions=["UVXY"], asset_type="etf", rules=rules())
        self.assertTrue(ex)
        self.assertEqual(reason, "listed_in_etf_exclusions")

    def test_price_and_volume_floors(self):
        self.assertFalse(universe.passes_liquidity_and_price(price=4.99, avg_daily_volume=2_000_000, rules=rules())[0])
        self.assertFalse(universe.passes_liquidity_and_price(price=5.0, avg_daily_volume=999_999, rules=rules())[0])
        self.assertTrue(universe.passes_liquidity_and_price(price=5.0, avg_daily_volume=1_000_000, rules=rules())[0])

    def test_trend_skips_holdings(self):
        self.assertTrue(universe.passes_trend_filter(close=10.0, sma_200=20.0, is_holding=True, rules=rules())[0])
        ok, reason = universe.passes_trend_filter(close=10.0, sma_200=20.0, is_holding=False, rules=rules())
        self.assertFalse(ok)
        self.assertEqual(reason, "below_sma_200")

if __name__ == "__main__":
    unittest.main()
