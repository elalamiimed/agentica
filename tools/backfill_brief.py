"""Backfill the source brief into an existing run's run_log.json.

Newer runs record the brief automatically. This is for bundles produced before that,
so tools/refresh_outputs.py can re-check them against the material they came from.

    <python> tools/backfill_brief.py <slug> <brief-file>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    slug, brief_file = argv
    folder = ROOT / "output" / slug
    run_log = folder / "run_log.json"
    if not run_log.is_file():
        print(f"no run_log.json in {folder}")
        return 1
    brief_text = Path(brief_file).read_text(encoding="utf-8-sig")
    data = json.loads(run_log.read_text(encoding="utf-8"))
    data["brief"] = {"raw_notes": brief_text, "doc_type": data.get("doc_type", "")}
    data["brief_text"] = brief_text
    run_log.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"backfilled {len(brief_text)} characters of brief into {run_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
