"""E (round 2): the form-level date warning, against the shared canonical date model.

Targets: month names that are ordinary words, year-vs-year, mixed notation, impossible dates,
and the exact wording the operator sees.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import form  # noqa: E402

BASE = {
    "event_name_en": "APEC Future Skills Challenge",
    "event_name_cn": "APEC 未来技能挑战赛",
    "doc_type": "回顾",
    "time_start": "15:00", "time_end": "18:00",
    "venue_en": "Room A509, HITSZ", "venue_cn": "哈工大（深圳）A509 教室",
    "participants": "32 contestants",
    "credit_writer": "Zhumabay Aruzhan", "credit_photo": "Yalalt",
    "credit_layout": "Najmia Popal", "credit_review1": "Samin",
    "credit_review2": "周宣彤", "credit_review3": "卢锦章",
}

CASES = [
    ("F1  month name used as a verb (march 5 km)",
     "2026-11-08", "", "The students march 5 kilometres to the hall before the event."),
    ("F2  month name used as a verb (may 8 people)",
     "2026-11-08", "", "May 8 people join us, and the rest come later."),
    ("F3  desc date == start, different notation",
     "2026-11-08", "", "活动于 2026/11/8 举行。"),
    ("F4  desc day == start day, no year in desc",
     "2026-11-08", "", "活动于 11月8日 举行。"),
    ("F5  desc has a different YEAR, same day",
     "2026-11-08", "", "The event was held on 8 November 2025."),
    ("F6  desc date == end of a 2-day event",
     "2026-11-08", "2026-11-09", "The second day, 11月9日, drew the bigger crowd."),
    ("F7  desc date == end, unrelated deadline",
     "2026-11-08", "2026-11-09", "报名截止 11月1日，活动 11月8日至9日。"),
    ("F8  impossible date in desc",
     "2026-11-08", "", "活动于 2026-02-30 举行。"),
    ("F9  desc with a registration deadline and the event date",
     "2026-11-08", "", "报名截止 2026年11月1日，活动于 2026年11月8日 举行。"),
    ("F10 real-world shape: full notes",
     "2026-11-08", "",
     "The first round happened in A509 on 8 November. 32 students signed up. "
     "Registration closed on 1 November."),
    ("F11 real-world shape: notes with a time range",
     "2026-11-08", "", "We ran the session 15:00-18:00 on 8 November in A509."),
    ("F12 desc matches start ISO exactly",
     "2026-11-08", "", "活动于 2026-11-08 举行。"),
    ("F13 desc date = start as 中文 with 号",
     "2026-11-08", "", "活动于 11月8号 举行。"),
]


def main() -> int:
    for label, start, end, description in CASES:
        answers = dict(BASE)
        answers["date_start"] = start
        answers["date_end"] = end
        answers["event_description"] = description
        ok, errors, warnings = form.validate_answers(answers)
        date_warnings = [w for w in warnings if "neither the start nor the end" in w]
        print(f"{label}")
        print(f"    description: {description!r}")
        print(f"    fields     : start={start!r} end={end!r}")
        print(f"    warned     : {bool(date_warnings)}"
              f"{'  -> ' + date_warnings[0][:120] if date_warnings else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
