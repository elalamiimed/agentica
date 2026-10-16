"""Exact, minimal reproductions for the confirmed defects.

    <python> _work/verify_develop/repro.py all
    <python> _work/verify_develop/repro.py <case-id>
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop, form  # noqa: E402

EMPTY = {"numbers": [], "dates": [], "names": []}

REPROS = {
    # ---------------------------------------------------------------- false positives
    "fp1": ("FP1 dates written two ways: a month/day digit escapes the blanking",
            lambda: develop.unsourced(
                "The event was held from 8 to 9 November.",
                "活动于11月8日至9日举行。"),
            EMPTY),
    "fp2": ("FP2 full-width digits in the notes are never matched by half-width digits in the rewrite",
            lambda: develop.unsourced("共有32名学生报名。", "共有３２名学生报名。"),
            EMPTY),
    "fp3": ("FP3 a month name used as an ordinary verb creates a phantom date",
            lambda: develop.unsourced(
                "We march five kilometres to the hall.",
                "We march 5 kilometres to the hall."),
            EMPTY),
    "fp4": ("FP4 a month name used as an ordinary verb accuses a faithful rewrite",
            lambda: develop.unsourced(
                "We march five kilometres to the hall.",
                "We march 5 kilometres to the hall."),
            EMPTY),
    "fp4b": ("FP4b same sentence, the month word removed: the warning disappears",
             lambda: develop.unsourced(
                 "They walk five kilometres to the hall.",
                 "They walk 5 kilometres to the hall."),
             EMPTY),
    "fp5": ("FP5 bare day in the notes vs a full date in the rewrite",
            lambda: develop.unsourced("首轮定在11月8日。", "首轮定在8号。"),
            EMPTY),
    "fp6": ("FP6 month-only note vs a full date in the rewrite",
            lambda: develop.unsourced("比赛于11月8日举行。", "比赛在11月。"),
            EMPTY),
    "fp7": ("FP7 an ordinary Chinese word is read as a figure (五官 -> 5)",
            lambda: develop.unsourced(
                "活动现场气氛热烈，五官精致的海报很受欢迎。",
                "活动现场气氛热烈，同学们同场竞技。"),
            EMPTY),
    # ---------------------------------------------------------------- warning false positive
    "fp8": ("FP8 the form date warning fires on 'march'/'May' as ordinary verbs",
            lambda: form.validate_answers({
                "event_name_en": "E", "event_name_cn": "活动", "doc_type": "回顾",
                "date_start": "2026-11-08", "date_end": "",
                "venue_en": "Room A509", "event_description": "The students march 5 kilometres.",
                "credit_writer": "A", "credit_photo": "B", "credit_layout": "C",
                "credit_review1": "D", "credit_review2": "E", "credit_review3": "F",
            })[2],
            "no date warning"),
    # ---------------------------------------------------------------- parse bug
    "fp9": ("FP9 '8th of November 2026' parses to November 20th",
            lambda: (sorted(develop._dates("8th of November 2026")[0]),
                     sorted(develop._dates("2026年11月8日")[0])),
            (["2026-11-08"], ["2026-11-08"])),
}


def main() -> int:
    wanted = sys.argv[1:] or ["all"]
    for key, (title, fn, expected) in REPROS.items():
        if "all" not in wanted and key not in wanted:
            continue
        try:
            observed = fn()
        except Exception as exc:  # a crash is itself the finding
            observed = f"{type(exc).__name__}: {exc}"
        print(f"\n=== {key}: {title}")
        print(f"  expected : {expected}")
        print(f"  observed : {observed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
