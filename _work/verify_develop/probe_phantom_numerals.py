"""The phantom-numeral false positive in validate.validate, on a clean article."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import validate  # noqa: E402

CREDITS = {"文字": "Zhumabay Aruzhan", "图片": "Yalalt", "排版": "Najmia Popal",
           "一审": "Samin、柯炽炜", "二审": "周宣彤、崔雨旸、高容驷", "三审": "卢锦章"}


def article(cn_body: str, en_body: str) -> dict:
    long_cn = cn_body * 3
    long_en = en_body * 4
    return {
        "meta": {"doc_type": "回顾"},
        "title": {"cn": "国际青年俱乐部 ｜活动回顾：技能挑战赛", "en": "HSIYC | Recap"},
        "lead": {"kind": "bilingual", "cn": "哈工大（深圳）国际青年俱乐部举办活动。",
                 "en": "HSIYC held the event."},
        "sections": [{
            "heading_cn": "活动详情", "heading_en": "Event details",
            "body": [{"kind": "bilingual", "cn": long_cn, "en": long_en}],
        } for _ in range(6)],
        "closing": {"kind": "bilingual", "cn": "活动圆满落幕。", "en": "The event concluded."},
        "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
        "credits": dict(CREDITS),
        "toc": {"previous": "", "next": ""},
        "facts": [{"fact": "x", "source": "brief"}],
        "needs_editor": ["confirm the count"],
    }


CASES = [
    ("plain copy, no numerals",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，现场气氛热烈，同学们收获很多。",
     "HSIYC held the event in A509 and the room was full of energy."),
    ("copy with 两国 (two countries)",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，来自两国的同学同场竞技，现场气氛热烈。",
     "HSIYC held the event in A509 where students from two countries competed."),
    ("copy with 十分感谢",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，十分感谢各位同学的参与和支持。",
     "HSIYC held the event in A509 and we thank every member who joined."),
    ("copy with 五官/三位",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，五官精致的海报很受欢迎，现场气氛热烈。",
     "HSIYC held the event in A509 and the poster was well received."),
]

BRIEF = {
    "doc_type": "回顾", "title_cn": "活动回顾", "title_en": "Recap",
    "event_date": "2026年11月8日", "venue": "哈工大（深圳）A509 教室",
    "organisers": ["哈工大（深圳）国际青年俱乐部（HSIYC）"], "credits": dict(CREDITS),
    "event_description": "活动在 A509 举行，气氛热烈，同学们收获很多。",
}


def main() -> int:
    for label, cn, en in CASES:
        report = validate.validate(copy.deepcopy(article(cn, en)), brief=dict(BRIEF))
        nums = [f for f in report.findings if f.code == "FACT-NUMBER"]
        print(f"{label:34} FACT-NUMBER: {nums[0].message if nums else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
