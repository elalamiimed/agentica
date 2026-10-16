"""Minimal, exact reproductions of the two validate-side false positives."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import validate  # noqa: E402
from hsiyc_writer.validate import STANDALONE_NUMBER_RE, number_words  # noqa: E402

CREDITS = {"文字": "Zhumabay Aruzhan", "图片": "Yalalt", "排版": "Najmia Popal",
           "一审": "Samin、柯炽炜", "二审": "周宣彤、崔雨旸、高容驷", "三审": "卢锦章"}

FILLER = ("哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，现场气氛热烈，同学们收获很多，"
          "感谢每一位成员的参与和支持，期待下一次相聚。")
FILLER_EN = ("HSIYC held the event in A509 and the room was full of energy. Thank you to every "
             "member who joined us and made the afternoon work. ")


def article(cn_body: str) -> dict:
    return {
        "meta": {"doc_type": "回顾"},
        "title": {"cn": "国际青年俱乐部 ｜活动回顾：技能挑战赛", "en": "HSIYC | Recap"},
        "lead": {"kind": "bilingual", "cn": FILLER, "en": FILLER_EN},
        "sections": [{
            "heading_cn": "活动详情", "heading_en": "Event details",
            "body": [{"kind": "bilingual", "cn": cn_body * 2, "en": FILLER_EN * 2}],
        } for _ in range(6)],
        "closing": {"kind": "bilingual", "cn": "活动圆满落幕。", "en": "The event concluded."},
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


def report_for(cn_body: str) -> None:
    brief_nums: set[str] = set()
    for value in validate._iter_scalars(BRIEF):
        brief_nums |= set(STANDALONE_NUMBER_RE.findall(value)) | number_words(value)
    body_words = number_words(cn_body * 2 + FILLER)
    print(f"  body words -> {sorted(body_words)}   brief words -> {sorted(number_words(' '.join(validate._iter_scalars(BRIEF))))}")
    print(f"  unexplained word-numbers: {sorted(body_words - brief_nums - {'1','2','3'})}")
    rep = validate.validate(copy.deepcopy(article(cn_body)), brief=copy.deepcopy(BRIEF))
    found = [f.message for f in rep.findings if f.code == "FACT-NUMBER"]
    print(f"  FACT-NUMBER: {found[0] if found else 'none'}")


print("=== case 1: 两国 in the article, 32 in the brief ===")
report_for("哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，来自两国的同学同场竞技，气氛热烈。")
print()
print("=== case 2: 五官 in the article, 32 in the brief ===")
report_for("哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，五官精致的海报很受欢迎，气氛热烈。")
print()
print("=== control: same article without 两国/五官 ===")
report_for("哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，同学们同场竞技，气氛热烈。")
