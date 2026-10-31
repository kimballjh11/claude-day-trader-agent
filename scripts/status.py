#!/usr/bin/env python3
"""Write status/last_run.json for the dashboard and next run."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "status" / "last_run.json"


def write_status(
    *,
    run: str,
    outcome: str,
    errors: Optional[list[dict]] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "run": run,
        "started_at": started_at or now,
        "finished_at": finished_at or now,
        "outcome": outcome,
        "errors": errors or [],
    }
    if extra:
        payload.update(extra)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATUS_PATH)
    return payload


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True, choices=["morning", "evening", "weekly", "manual"])
    p.add_argument("--outcome", required=True,
                   choices=["ok", "warning", "error", "market_closed", "TESTS_FAILED"])
    p.add_argument("--error-code", action="append", default=[])
    p.add_argument("--error-text", action="append", default=[])
    args = p.parse_args(argv)

    errors = []
    for i, code in enumerate(args.error_code):
        text = args.error_text[i] if i < len(args.error_text) else code
        errors.append(
            {
                "severity": "error" if args.outcome == "error" else "warning",
                "code": code,
                "text": text,
                "at": datetime.now(timezone.utc).isoformat(),
                "run": args.run,
            }
        )

    payload = write_status(run=args.run, outcome=args.outcome, errors=errors)
    print(json.dumps({"ok": True, "path": str(STATUS_PATH), "status": payload}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
