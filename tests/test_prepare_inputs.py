#!/usr/bin/env python3
import sys, unittest
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "atd"))
import prepare_inputs as pi

def _bar(day, close, interpolated=False):
    return {"begins_at": f"{day}T14:30:00.000000Z", "close_price": str(close), "interpolated": interpolated}

class TestPrepareInputs(unittest.TestCase):
    def test_drops_interpolated_bars(self):
        hist = [{"symbol":"TEST","bars":[_bar("2026-01-02",10.0,True),_bar("2026-01-05",11.0),_bar("2026-01-06",12.0)]}]
        now = datetime.fromisoformat("2026-01-06T21:00:00+00:00")
        rep = pi.prepare(hist, [], now)["symbols"]["TEST"]
        self.assertEqual(rep["status"], "ok")
        self.assertEqual(rep["interpolated_dropped"], 1)
        self.assertEqual(rep["_close"], [11.0, 12.0])

    def test_stale_symbol_excluded(self):
        hist = [{"symbol":"OLD","bars":[_bar("2026-01-02",10.0),_bar("2026-01-05",11.0)]}]
        quotes = [{"quote":{"symbol":"OLD","previous_close_date":"2026-01-08","last_trade_price":"12.0",
            "venue_last_trade_time":"2026-01-08T15:00:00.000000-05:00"}}]
        now = datetime.fromisoformat("2026-01-08T21:00:00+00:00")
        rep = pi.prepare(hist, quotes, now)["symbols"]["OLD"]
        self.assertEqual(rep["status"], "excluded")
        self.assertTrue(any("STALE" in w for w in rep["warnings"]))

if __name__ == "__main__":
    unittest.main()
