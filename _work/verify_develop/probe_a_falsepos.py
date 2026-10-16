"""A. Adversarial hunt for FALSE POSITIVES in develop.unsourced().

Each case is (label, source_notes, faithful_rewrite). A faithful rewrite must yield
{"numbers": [], "dates": [], "names": []}.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop  # noqa: E402

CASES: list[tuple[str, str, str]] = [
    # ---- date notation equivalence ------------------------------------------
    ("A1 月日 vs ISO",
     "The workshop ran on 8 November in A509.",
     "The workshop ran on 2026-11-08 in A509."),
    ("A2 月日 vs 斜杠",
     "The workshop ran on 8 November in A509.",
     "The workshop ran on 2026/11/8 in A509."),
    ("A3 中文 vs 英文",
     "活动于 11月8日 在 A509 举行。",
     "The event was held on 8 November in A509."),
    ("A4 中文年份 vs 英文",
     "活动于 2026年11月8日 在 A509 举行。",
     "The event was held on 8 November 2026 in A509."),
    ("A5 号 vs 日",
     "活动于 11月8号 在 A509 举行。",
     "活动于 11月8日 在 A509 举行。"),
    ("A6 月在前 vs 日在前后缀",
     "The event is on Nov 8.",
     "The event is on 8th November 2026."),
    ("A7 中文年份 vs ISO",
     "活动于 2026年11月8日 在 A509 举行。",
     "The event was held on 2026-11-08 in A509."),
    ("A8 ISO vs 中文",
     "The event was held on 2026-11-08 in A509.",
     "活动于 2026年11月8日 在 A509 举行。"),
    ("A9 完整英文 vs 中文月日",
     "The finals were on November 8, 2026.",
     "The finals were on 11月8日."),
    # ---- numbers in labels / rooms / codes -----------------------------------
    ("A10 room + time + label",
     "Round one in A509, 15:00-18:00, 1v1 blitz, 90 seconds each.",
     "The first round took place in A509 from 15:00-18:00. It was a 1v1 blitz with 90 seconds each."),
    ("A11 双打12对",
     "羽毛球双打12对，单打8人。",
     "羽毛球项目设双打12对、单打8人。"),
    ("A12 3号场",
     "比赛在 3号场 进行，共 12 对选手。",
     "比赛在 3号场 进行，共 12 对选手参加。"),
    ("A13 Room 3 / five minutes",
     "We met in Room 3 for five minutes.",
     "The team met in Room 3 for 5 minutes."),
    # ---- spelt vs digits -----------------------------------------------------
    ("A14 twelve pairs",
     "双打12对。",
     "Twelve pairs played doubles."),
    ("A15 三十 vs 30",
     "共有三十名学生报名。",
     "A total of 30 students signed up."),
    ("A16 三十二 vs 32",
     "共有三十二名学生报名。",
     "A total of 32 students signed up."),
    ("A17 twelfth (ordinal into a date)",
     "The gala is on November 12.",
     "The gala is on the twelfth of November."),
    ("A18 five in a date-ish phrase",
     "The club has five members and meets on 5 November.",
     "The club has 5 members and meets on November 5."),
    # ---- full-width digits ---------------------------------------------------
    ("A19 全角数字 -> 半角",
     "共有３２名学生报名，在 A509 举行。",
     "共有32名学生报名，在 A509 举行。"),
    ("A20 全角与半角标点",
     "活动于 11月8日（周六）14:00 举行。",
     "活动于 11月8日（周六）14:00 举行。"),
    # ---- month words that are ordinary words ---------------------------------
    ("A21 May as a verb",
     "May I add that 8 students came? The event was on 8 November.",
     "May I add that eight students came? The event was on 8 November."),
    ("A22 March as a verb",
     "The students march 5 kilometres, then the event on March 5 begins.",
     "The students march five kilometres, then the event on March 5 begins."),
    # ---- time-only source ----------------------------------------------------
    ("A23 time-only notes",
     "The session ran 15:00 to 18:00 in A509.",
     "The session ran from 15:00 to 18:00 in A509."),
    ("A24 time-only, date added in rewrite",
     "The session ran from 15:00 to 18:00.",
     "On 8 November the session ran from 15:00 to 18:00."),
    # ---- extra invented shapes I added --------------------------------------
    ("A25 ISO in source, 月日 in rewrite",
     "The event was held on 2026-11-08.",
     "活动于 11月8日 举行。"),
    ("A26 year-only change",
     "The event was held on 8 November 2026.",
     "The event was held on November 8, 2026."),
    ("A27 hyphenated serial numbers",
     "Buses 2026-11-08 and 2026-11-09 were booked.",
     "Buses 2026-11-08 and 2026-11-09 were booked for the trip."),
    ("A28 decimal number",
     "The average score was 5.5 points.",
     "The average score was 5.5 points overall."),
    ("A29 percent and ratio",
     "About 80% of the 32 students, a 1:4 ratio.",
     "About 80% of the 32 students, a 1:4 ratio."),
    ("A30 half-width punctuation tidy",
     "活动于11月8日举行,地点A509.共32人参加.",
     "活动于11月8日举行，地点A509。共32人参加。"),
]


def main() -> int:
    bad = 0
    for label, source, rewrite in CASES:
        result = develop.unsourced(rewrite, source)
        clean = result == {"numbers": [], "dates": [], "names": []}
        if not clean:
            bad += 1
        print(f"{'CLEAN ' if clean else 'FP    '} {label}")
        if not clean:
            print(f"        source : {source!r}")
            print(f"        rewrite: {rewrite!r}")
            print(f"        result : {result}")
            print(f"        dates(src)={sorted(develop._dates(source)[0])} "
                  f"dates(rw)={sorted(develop._dates(rewrite)[0])}")
            print(f"        figs(src)={sorted(develop._figures(source))} "
                  f"figs(rw)={sorted(develop._figures(rewrite))}")
    print(f"\n{bad} false positive(s) out of {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
