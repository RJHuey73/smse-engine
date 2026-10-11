"""``python -m smse_engine.cli RAW.json --timestamp ... --date ...`` -> JSON on stdout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from smse_engine.pipeline import run_pipeline
from smse_engine.schema import RawBundle


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="smse-engine")
    p.add_argument("raw", type=Path, help="JSON object: {asset: RawBundle}")
    p.add_argument("--timestamp", required=True, help="ISO-8601 UTC, e.g. 2026-04-30T21:00:00Z")
    p.add_argument("--date", required=True, help="brief date, e.g. 2026-04-30")
    p.add_argument("--text", action="store_true", help="print brief_text only")
    a = p.parse_args(argv)
    data = json.loads(a.raw.read_text())
    raw = {k: RawBundle.model_validate(v) for k, v in data.items()}
    res = run_pipeline(raw, a.timestamp, a.date)
    if a.text:
        sys.stdout.write(res.brief.brief_text)
    else:
        out = {"records": [r.model_dump(mode="json") for r in res.records], "brief": res.brief.model_dump(mode="json")}
        sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
