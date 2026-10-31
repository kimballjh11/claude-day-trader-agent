#!/usr/bin/env python3
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sector_cap

class TestSectorCap(unittest.TestCase):
    def test_fourth_in_sector_blocked(self):
        out = sector_cap.filter_by_sector_cap(
            [{"symbol":"A","group":"new","sector":"Technology"}],
            held_sectors=["Technology"]*3, max_per_sector=3)
        self.assertFalse(out[0]["sector_cap_passed"])

    def test_third_allowed(self):
        out = sector_cap.filter_by_sector_cap(
            [{"symbol":"A","group":"new","sector":"Technology"}],
            held_sectors=["Technology"]*2, max_per_sector=3)
        self.assertTrue(out[0]["sector_cap_passed"])

    def test_etf_mapping(self):
        self.assertEqual(sector_cap.resolve_sector("SPY", asset_type="etf"), "Broad Market")
        self.assertEqual(sector_cap.resolve_sector("XLK", asset_type="etf", etf_sectors={"XLK":"Technology"}), "Technology")
        self.assertEqual(sector_cap.resolve_sector("XYZETF", asset_type="etf"), "Other ETF")

    def test_unknown_counts(self):
        out = sector_cap.filter_by_sector_cap(
            [{"symbol":"Z","group":"new","sector":"Unknown"}],
            held_sectors=["Unknown"]*3, max_per_sector=3)
        self.assertFalse(out[0]["sector_cap_passed"])

    def test_held_top_up_does_not_increment(self):
        out = sector_cap.filter_by_sector_cap(
            [{"symbol":"AAPL","group":"held","sector":"Technology"}],
            held_sectors=["Technology"]*3, max_per_sector=3)
        self.assertTrue(out[0]["sector_cap_passed"])

    def test_sp500_preferred_over_mcp_sector(self):
        sector = sector_cap.resolve_sector(
            "AAPL",
            asset_type="stock",
            mcp_sector="Electronic Technology",
            sp500_sectors={"AAPL": "Information Technology"},
        )
        self.assertEqual(sector, "Information Technology")

if __name__ == "__main__":
    unittest.main()
