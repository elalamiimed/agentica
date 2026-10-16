"""A (round 2): sharper false-positive hunt + explicit label/format probes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop, validate  # noqa: E402
from hsiyc_writer.validate import number_words  # noqa: E402

CASES: list[tuple[str, str, str]] = [
    ("B1 bare day -> full date",
     "The opening round is on the 8th.",
     "The opening round is on 11月8日."),
    ("B2 bare day (CN) -> full date",
     "首轮定在8号。",
     "首轮定在11月8日。"),
    ("B3 month-only -> full date",
     "The finals are in November.",
     "The finals are on 8 November."),
    ("B4 month-only CN -> full date",
     "比赛在11月。",
     "比赛于11月8日举行。"),
    ("B5 full-width digits in a label",
     "共有３２人报名。",
     "共有32人报名。"),
    ("B6 full-width digits in a room",
     "地点在Ａ５０９。",
     "地点在A509。"),
    ("B7 full-width digits in a count",
     "共５道题。",
     "共5道题。"),
    ("B8 march the verb + March the month",
     "We march 5 km on 8 November.",
     "We march five kilometres on 8 November."),
    ("B9 march the verb, no month after",
     "We march 5 kilometres to the hall.",
     "We march five kilometres to the hall."),
    ("B10 May at sentence start",
     "May I say 8 students came?",
     "May I say eight students came?"),
    ("B11 date range, day written twice",
     "The fair ran 8-9 November.",
     "The fair ran on 8 and 9 November."),
    ("B12 CN date range vs EN range",
     "活动于11月8日至9日举行。",
     "The event ran from 8 to 9 November."),
    ("B13 ISO in notes, ISO in rewrite, different separator",
     "The event was held on 2026-11-08.",
     "The event was held on 2026.11.8."),
    ("B14 two dates, order swapped",
     "Registration closes 1 November; the event is 8 November.",
     "The event is on 8 November; registration closes on 1 November."),
    ("B15 CN label 3号场 + English rewrite",
     "比赛在3号场举行，共12对。",
     "The match took place on court 3, with 12 pairs."),
    ("B16 time range only, no date",
     "The session ran 15:00 to 18:00.",
     "The session ran from 15:00 to 18:00."),
    ("B17 time range with 至",
     "活动时间为15:00至18:00。",
     "活动时间为15:00至18:00，共三小时。"),
    ("B18 half-width colon tidy in CN",
     "活动时间15:00-18:00,地点A509.",
     "活动时间15:00-18:00，地点A509。"),
    ("B19 ordinal written as word",
     "The 3rd round is on 8 November.",
     "The third round is on 8 November."),
    ("B20 score kept, hyphen",
     "The final ended 11-9.",
     "The final ended 11-9 in the third set."),
    ("B21 score rewritten as words",
     "The final ended 11-9.",
     "The final ended eleven to nine."),
    ("B22 pinyin name kept in Latin",
     "ling yi laoshi judged the finals on 8 November.",
     "Ling Yi laoshi judged the finals on 8 November."),
    ("B23 two-word Latin name kept",
     "Judge Alan Turing scored 32 entries.",
     "Judge Alan Turing scored 32 entries in total."),
    ("B24 name with middle initial",
     "Brandon M Yunata took second place with 32 points.",
     "Brandon M Yunata took second place with 32 points."),
    ("B25 abbreviations in a rewrite",
     "We ran a 1v1 blitz in A509 with 32 students.",
     "The 1v1 blitz ran in room A509 with 32 students."),
    ("B26 number in a code",
     "Ticket code HS-2026-11-08 was used.",
     "Ticket code HS-2026-11-08 was used."),
    ("B27 percentage kept",
     "80% of the 32 students stayed.",
     "Eighty percent of the 32 students stayed."),
    ("B28 十二 vs 12 inside a date-ish label",
     "第12届比赛于11月8日举行。",
     "The 12th edition was held on 8 November."),
]


def main() -> int:
    bad = 0
    for label, source, rewrite in CASES:
        result = develop.unsourced(rewrite, source)
        clean = result == {"numbers": [], "dates": [], "names": []}
        if not clean:
            bad += 1
        print(f"{'CLEAN' if clean else 'FP   '} {label}")
        if not clean:
            print(f"        source : {source!r}")
            print(f"        rewrite: {rewrite!r}")
            print(f"        result : {result}")
            print(f"        dates(src)={sorted(develop._dates(source)[0])} dates(rw)={sorted(develop._dates(rewrite)[0])}")
            print(f"        figs(src)={sorted(develop._figures(source))} figs(rw)={sorted(develop._figures(rewrite))}")
    print(f"\n--- extra: full-width digit understanding ---")
    for text in ("３２", "32", "３２人", "32人"):
        print(f"  _figures({text!r}) = {sorted(develop._figures(text))}  "
              f"number_words={sorted(number_words(text))}  "
              f"STANDALONE={sorted(validate.STANDALONE_NUMBER_RE.findall(text))}")
    print(f"\n--- extra: 三十二 vs 32 ---")
    for text in ("三十二名", "32名", "九十秒", "90秒"):
        print(f"  number_words({text!r}) = {sorted(number_words(text))}")
    print(f"\n{bad} false positive(s) out of {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
