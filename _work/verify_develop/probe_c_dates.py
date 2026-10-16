"""C. develop._dates() / _blank() / _figures(): crashes, spans, off-by-one."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop  # noqa: E402

INPUTS = [
    "2026年11月8日至9日",
    "2026年11月8日",
    "活动于2026年11月8日",
    "2026年11月8日举行活动",
    "",
    None,
    "13月45日",
    "2026-13-45",
    "2026年13月45日",
    "0月0日",
    "11月0日",
    "11月32日",
    "2026-02-30",
    "2026年11月8",
    "11月",
    "November",
    "8 November 2026 and 9 November 2026",
    "2026-11-08 2026-11-09",
    "1月1日1月2日",
    "2026年11月8日2026年11月9日",
    "31 February",
    "9999年99月99日",
    "2026/11/8 and 2026.11.9",
    "ab8 Novembercd",
    "8Nov",
    "Nov8",
    "the 8th of November",
    "8th of November 2026",
    "May 5, 2026 and march 5 km",
    "2026年11月8日至2026年11月9日",
    "12月31日",
    "1月1日",
    "2026-1-1",
    "2026-01-01",
    "January 1",
    "jan 1",
    "sept 9",
    "sept. 9",
    "Sept. 9, 2026",
    "8 Nov.",
    "8 Nov. 2026",
    "2026年11月08日",
    "２０２６年１１月８日",
    "11月8号",
    "11月8號",
    " 2026年11月8日 ",
    "\n2026年11月8日\n",
    "2026年11月8日、11月9日",
    "报名截止11月1日，活动11月8日",
    "11月8日11月9日",
    "29 February 2026",
    "29 February 2024",
]


def show(label: str, value) -> None:
    try:
        dates, spans = develop._dates(value)
    except Exception:
        print(f"CRASH _dates({label}): {traceback.format_exc().splitlines()[-1]}")
        return
    try:
        blanked = develop._blank(value, spans)
    except Exception:
        print(f"CRASH _blank({label}): {traceback.format_exc().splitlines()[-1]}")
        return
    try:
        figs = develop._figures(value)
    except Exception:
        print(f"CRASH _figures({label}): {traceback.format_exc().splitlines()[-1]}")
        return
    length_ok = (value is None and blanked == "") or (isinstance(value, str) and len(blanked) == len(value))
    print(f"{label!r:44} dates={sorted(dates)!s:28} spans={spans!s:20} "
          f"len_ok={length_ok} blanked={blanked!r} figs={sorted(figs)}")
    if not length_ok:
        print(f"    !! _blank changed the string length: {len(value)} -> {len(blanked)}")


def main() -> int:
    print("=== _dates / _blank / _figures over awkward inputs ===")
    for value in INPUTS:
        show(str(value), value)

    print("\n=== span sanity: does _blank blank exactly the digits it found? ===")
    for value in ("2026年11月8日", "8 November 2026", "Nov 8, 2026", "2026-11-08",
                  "11月8日", "2026年11月8日至9日", "2026/11/8"):
        dates, spans = develop._dates(value)
        blanked = develop._blank(value, spans)
        removed = [value[i] for i, (a, b) in enumerate(
            [(s, e) for s, e in spans]) for i in range(a, min(len(value), b))]
        print(f"  {value!r:26} -> {blanked!r:26} blanked_chars={removed}")

    print("\n=== overlap / adjacency: the 9 of a range ===")
    for value in ("2026年11月8日至9日", "8-9 November", "8 and 9 November",
                  "11月8日、9日", "2026年11月8日-9日"):
        dates, spans = develop._dates(value)
        print(f"  {value!r:28} dates={sorted(dates)} blanks={spans} "
              f"figures={sorted(develop._figures(value))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
