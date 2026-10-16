"""B. FALSE NEGATIVES in develop.unsourced(): invented facts that pass silently.

Each case is an intentionally DISHONEST rewrite. A 'FALSE NEGATIVE' line means the check
reported nothing at all; 'partly seen' means it caught some but not the invented fact.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop  # noqa: E402

CASES: list[tuple[str, str, str, str]] = [
    # (label, source, dishonest rewrite, the invented fact)
    ("C1 unit swapped, digit kept",
     "32 students signed up for the blitz.",
     "Thirty-two pairs signed up for the blitz.",
     "students -> pairs"),
    ("C2 single-word name substituted",
     "Tugsuu beat Brandon in the final.",
     "Michael beat Brandon in the final.",
     "Tugsuu -> Michael"),
    ("C3 single-word name invented",
     "The final was decided on the last integral.",
     "Aruzhan won the final on the last integral.",
     "invented winner Aruzhan"),
    ("C4 invented venue",
     "The event happened in A509.",
     "The event happened in the Grand Ballroom in A509.",
     "invented venue"),
    ("C5 invented score",
     "The final was close.",
     "The final ended 11-9 in a tiebreak.",
     "invented score 11-9"),
    ("C6 invented score, digits in the notes",
     "The final was close; 32 people watched.",
     "The final ended 9-11 in front of 32 people.",
     "invented score 9-11"),
    ("C7 date digits reordered",
     "The event was held on 11月8日.",
     "The event was held on 8月11日.",
     "11月8日 -> 8月11日"),
    ("C8 date shifted by a year, month/day kept",
     "The event was held on 8 November 2026.",
     "The event was held on 8 November 2025.",
     "year changed 2026 -> 2025"),
    ("C9 pinyin name turned into characters",
     "ling yi laoshi judged the finals.",
     "凌一老师 judged the finals.",
     "ling yi -> 凌一"),
    ("C10 invented Chinese winner",
     "The event was held on 8 November.",
     "活动于8月11日举行，王梓涵获得冠军。",
     "invented winner 王梓涵"),
    ("C11 invented count in a unit-free sentence",
     "A large crowd stayed to the end.",
     "Eighty people stayed to the end.",
     "invented count eighty"),
    ("C12 invented country",
     "Students from seven countries took part.",
     "Students from nine countries took part.",
     "seven -> nine"),
    ("C13 invented sponsor",
     "The club organised the blitz.",
     "The club organised the blitz with AcademiaSphere.",
     "invented sponsor"),
    ("C14 invented quote",
     "The judge gave feedback afterwards.",
     "The judge said the level was impressive afterwards.",
     "invented quote-ish claim"),
    ("C15 invented date as a digit-only string",
     "The event was held on 8 November in A509.",
     "The event was held on 9/11/2026 in A509.",
     "invented date 9/11/2026"),
    ("C16 invented rank",
     "Tugsuu took the final.",
     "Tugsuu took the final and was named champion of the region.",
     "invented rank"),
    ("C17 invented decimal score",
     "The team scored well.",
     "The team scored 5.5 points.",
     "invented score 5.5"),
    ("C18 invented room in the same building",
     "The event happened in A509.",
     "The event happened in A509 and in B712.",
     "invented room B712"),
    ("C19 invented time",
     "The session ran in the afternoon.",
     "The session ran from 15:00 to 18:00.",
     "invented times"),
    ("C20 invented prize",
     "Tugsuu won the final.",
     "Tugsuu won the final and took the 500 yuan prize.",
     "invented prize 500"),
]


def main() -> int:
    print(f"{'label':38} {'reported':>10}  detail")
    print("-" * 100)
    for label, source, rewrite, invented in CASES:
        result = develop.unsourced(rewrite, source)
        total = sum(len(v) for v in result.values())
        verdict = "FALSE NEGATIVE" if total == 0 else "partly seen"
        print(f"{label:38} {total:>10}  {verdict}")
        print(f"    invented fact  : {invented}")
        print(f"    source         : {source!r}")
        print(f"    rewrite        : {rewrite!r}")
        print(f"    unsourced      : {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
