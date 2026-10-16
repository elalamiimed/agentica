"""Exact, length-valid reproductions of the CJK-numeral false positive in validate."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import validate  # noqa: E402

CREDITS = {"文字": "Zhumabay Aruzhan", "图片": "Yalalt", "排版": "Najmia Popal",
           "一审": "Samin、柯炽炜", "二审": "周宣彤、崔雨旸、高容驷", "三审": "卢锦章"}

PAD_CN = ("哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，现场气氛热烈，同学们收获很多，"
          "感谢每一位成员的参与和支持，期待下一次相聚。") * 3
PAD_EN = ("HSIYC held the event in A509 and the room was full of energy. Thank you to every "
          "member who joined us and made the afternoon work. ") * 3


def article(cn_body: str) -> dict:
    return {
        "meta": {"doc_type": "回顾"},
        "title": {"cn": "国际青年俱乐部 ｜活动回顾：技能挑战赛", "en": "HSIYC | Recap"},
        "lead": {"kind": "bilingual", "cn": PAD_CN, "en": PAD_EN},
        "sections": [
            {"heading_cn": "活动详情", "heading_en": "Event details",
             "body": [{"kind": "bilingual", "cn": cn_body + PAD_CN, "en": PAD_EN}]}
            for _ in range(6)
        ],
        "closing": {"kind": "bilingual", "cn": PAD_CN, "en": PAD_EN},
        "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
        "credits": dict(CREDITS), "toc": {"previous": "", "next": ""},
        "facts": [{"fact": "x", "source": "brief"}], "needs_editor": ["confirm the count"],
    }


BRIEF = {
    "doc_type": "回顾", "title_cn": "活动回顾", "title_en": "Recap",
    "event_date": "2026年11月8日", "venue": "哈工大（深圳）A509 教室",
    "organisers": ["哈工大（深圳）国际青年俱乐部（HSIYC）"],
    "participants_count": "32 名选手", "credits": dict(CREDITS),
    "event_description": "活动在 A509 举行，32 名选手参加。",
}

VARIANTS = [
    ("control (no numeral-shaped word)",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，同学们同场竞技，气氛热烈。"),
    ("with 五官 (facial features)",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，五官精致的海报很受欢迎，气氛热烈。"),
    ("with 三次 (three times)",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，活动共三次，气氛热烈。"),
    ("with 十分 (very)",
     "哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，十分感谢各位同学的参与，气氛热烈。"),
]


def main() -> int:
    for label, body in VARIANTS:
        rep = validate.validate(copy.deepcopy(article(body)), brief=copy.deepcopy(BRIEF))
        nums = [f.message for f in rep.findings if f.code == "FACT-NUMBER"]
        print(f"{label:34} -> {nums[0] if nums else 'no FACT-NUMBER'}")
        print(f"{'':34}    score={rep.score} errors={len(rep.errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
