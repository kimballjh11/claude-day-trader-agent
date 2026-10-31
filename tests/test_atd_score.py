#!/usr/bin/env python3
import subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "atd" / "score.py"

class TestAtdScore(unittest.TestCase):
    def test_self_test_passes(self):
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertTrue(len(proc.stdout) > 0)

if __name__ == "__main__":
    unittest.main()
