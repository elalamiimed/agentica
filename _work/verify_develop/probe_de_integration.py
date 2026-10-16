"""D + E: form -> brief -> article prompt integration, and the description whitelist.

D1: the operator's text reaches the text brief, the structured brief, and the article prompt.
D2: a fabricated figure placed in the description box whitelists itself for validate.validate
    (design consequence, with evidence).
D3: can the MODEL (not the operator) inject material into the whitelist?  The structured-brief
    normaliser path is the candidate: brief["event_description"] is authored by the model.
E1: the form-level full-date warning.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import form, prompts, validate  # noqa: E402

DESC = ("The first round of the APEC Future Skills Challenge finally happened in A509 on "
        "8 November. 32 students from 7 countries signed up and we ran it as a 1v1 blitz: "
        "five integrals, 90 seconds each. 凌怡老师 judged the final.")

ANSWERS = {
    "event_description": DESC,
    "event_name_en": "APEC Future Skills Challenge",
    "event_name_cn": "APEC 未来技能挑战赛",
    "doc_type": "回顾",
    "date_start": "2026-11-08",
    "date_end": "",
    "time_start": "15:00",
    "time_end": "18:00",
    "venue_en": "Room A509, HITSZ",
    "venue_cn": "哈工大（深圳）A509 教室",
    "organisers": "HITSZ International Youth Club (HSIYC)",
    "co_organisers": "",
    "participants": "32 contestants, about 80 audience members",
    "judges": "凌怡老师 (Professor Ling Yi) — judge",
    "winners": "Champion — Tugsuu Rentsennatsag",
    "highlights": "The 1v1 blitz format drew the biggest crowd",
    "results_summary": "",
    "programme": "APEC Smart Campus Innovation Series",
    "toc_previous": "",
    "toc_next": "",
    "contacts": "",
    "credit_writer": "Zhumabay Aruzhan",
    "credit_photo": "Yalalt",
    "credit_layout": "Najmia Popal",
    "credit_review1": "Samin、柯炽炜",
    "credit_review2": "周宣彤、崔雨旸、高容驷",
    "credit_review3": "卢锦章",
}


def minimal_article(number: str) -> dict:
    """Small bilingual article whose ONLY unexplained figure is `number`."""
    block = lambda cn, en: {"kind": "bilingual", "cn": cn, "en": en}  # noqa: E731
    sections = []
    for i in range(6):
        sections.append({
            "heading_cn": f"第{i+1}节 活动详情",
            "heading_en": f"Section {i+1} details",
            "body": [block(
                f"哈工大（深圳）国际青年俱乐部 HSIYC 于 2026年11月8日 在 A509 举办活动，"
                f"{number} 名同学参加，现场气氛热烈，大家收获很多，活动取得圆满成功。"
                + "感谢各位同学的支持与参与，期待下一次相聚。" * 3,
                f"HITSZ International Youth Club HSIYC held the event on 8 November 2026 in A509 "
                f"with {number} participants. The room was full and everyone enjoyed the session. "
                + "Thank you to every member who joined us and made the afternoon work. " * 4,
            )],
        })
    return {
        "meta": {"doc_type": "回顾", "date": "2026年11月8日"},
        "title": {"cn": "国际青年俱乐部 ｜活动回顾：APEC 未来技能挑战赛", "en": "HSIYC | Recap"},
        "lead": block("哈工大（深圳）国际青年俱乐部举办 APEC 未来技能挑战赛。",
                      "HSIYC held the APEC Future Skills Challenge."),
        "sections": sections,
        "closing": block("活动圆满落幕，感谢大家的参与。", "The event concluded successfully."),
        "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
        "credits": {
            "文字": "Zhumabay Aruzhan", "图片": "Yalalt", "排版": "Najmia Popal",
            "一审": "Samin、柯炽炜", "二审": "周宣彤、崔雨旸、高容驷", "三审": "卢锦章",
        },
        "toc": {"previous": "", "next": ""},
        "facts": [{"fact": "the event happened", "source": "brief"}],
        "needs_editor": [],
    }


def number_findings(article: dict, brief: dict) -> list[str]:
    report = validate.validate(copy.deepcopy(article), brief=brief)
    return [f.message for f in report.findings if f.code in ("FACT-NUMBER", "FACT-NAME")]


def main() -> int:
    print("################ D1: does the description reach all three consumers?")
    brief_text = form.answers_to_brief(ANSWERS)
    structured = form.answers_to_structured_brief(ANSWERS)
    messages = prompts.build_article_messages(structured, brief_text, [], doc_type="回顾")
    prompt = messages[-1]["content"]

    needle = "APEC Future Skills Challenge finally happened in A509 on"
    print(f"  text brief         contains description body : {needle in brief_text}")
    print(f"  text brief         has EVENT DESCRIPTION head : "
          f"{'EVENT DESCRIPTION' in brief_text}")
    print(f"  structured brief   event_description          : "
          f"{structured.get('event_description', '')[:40]!r}...")
    print(f"  structured brief   exact match                : "
          f"{structured.get('event_description') == DESC.strip()}")
    header = "THE CLUB'S OWN DESCRIPTION OF THE EVENT"
    print(f"  article prompt     CLUB'S OWN DESCRIPTION hdr : {header in prompt}")
    print(f"  article prompt     description body present   : {needle in prompt}")
    print(f"  article prompt     raw notes block present    : "
          f"{'RAW NOTES FROM THE CLUB' in prompt}")
    # every line of the description survives into both
    missing_brief = [ln for ln in DESC.splitlines() if ln.strip() and ln.strip() not in brief_text]
    missing_prompt = [ln for ln in DESC.splitlines() if ln.strip() and ln.strip() not in prompt]
    print(f"  text brief         lines dropped              : {missing_brief}")
    print(f"  article prompt     lines dropped              : {missing_prompt}")

    print("\n################ D2: a fabricated figure in the description box")
    for number, where in (("137", "only in event_description"),
                          ("211", "nowhere at all")):
        answers = dict(ANSWERS)
        answers["event_description"] = DESC + f" {number} volunteers helped on the day."
        brief = form.answers_to_structured_brief(answers)
        article = minimal_article(number)
        findings = number_findings(article, brief)
        print(f"  body says {number} ({where}): findings = {findings or 'NONE - passes'}")

    print("\n  control: the same article checked with a brief that does NOT come from the form")
    bare_brief = dict(structured)
    bare_brief["event_description"] = ""
    findings = number_findings(minimal_article("137"), bare_brief)
    print(f"    event_description cleared -> findings = {findings or 'NONE - passes'}")

    print("\n################ D3: can the MODEL inject into the whitelist?")
    # The normaliser path: model-authored prose becomes the structured brief.
    model_brief_text = ("We had a great night. I do not have the exact participant count, "
                        "but it felt like a big crowd.")
    model_structured = {
        "doc_type": "回顾",
        "event_description": "The club ran its annual gala; 137 members attended and "
                             "Prof. Lin Wei spoke.",
        "title_cn": "国际青年俱乐部 ｜活动回顾：年度晚会",
        "title_en": "HSIYC | Recap: Annual Gala",
        "event_date": "2026年11月8日",
        "event_time": "15:00-18:00",
        "venue": "哈工大（深圳）A509 教室",
        "venue_en": "Room A509, HITSZ",
        "organisers": ["哈工大（深圳）国际青年俱乐部（HSIYC）"],
        "partners": [],
        "participants_count": "",
        "judges": [],
        "winners": [],
        "programme": "",
        "highlights": [],
        "results_summary": "",
        "contacts": [],
        "credits": dict(ANSWERS and {"文字": "Zhumabay Aruzhan", "图片": "Yalalt",
                                     "排版": "Najmia Popal", "一审": "Samin、柯炽炜",
                                     "二审": "周宣彤、崔雨旸、高容驷", "三审": "卢锦章"}),
        "toc": {"previous": "", "next": ""},
        "photo_notes": [],
        "missing": [],
        "from_form": False,
    }
    article = minimal_article("137")
    findings = number_findings(article, model_structured)
    print(f"  model-authored brief['event_description'] carries 137 -> findings = "
          f"{findings or 'NONE - the model whitelisted its own figure'}")
    print(f"  (the operator's raw notes mention no count: {model_brief_text[:38]!r}...)")

    print("\n################ E: the form-level full-date warning")
    e_cases = [
        ("E1 description date == date_start", "2026-11-08", "", "活动于 2026年11月8日 举行。"),
        ("E2 description date == date_end of a range", "2026-11-08", "2026-11-21", "活动于 11月21日 结束。"),
        ("E3 description date differs from date_start", "2026-11-08", "", "活动于 2026年11月9日 举行。"),
        ("E4 description with no full date", "2026-11-08", "", "活动在11月举行，具体日期待定。"),
        ("E5 description month only, no day", "2026-11-08", "", "The finals are in November."),
        ("E6 invalid date 2026-13-45 in description", "2026-11-08", "", "活动于 2026-13-45 举行。"),
        ("E7 invalid date 13月45日 in description", "2026-11-08", "", "活动于 13月45日 举行。"),
        ("E8 invalid date 2026-02-30 in description", "2026-11-08", "", "活动于 2026-02-30 举行。"),
        ("E9 description date matches ISO field exactly", "2026-11-08", "", "活动于 2026-11-08 举行。"),
        ("E10 description date == date_start written CN", "2026-11-08", "", "活动于 2026年11月8日 举行。"),
        ("E11 description mentions an unrelated deadline", "2026-11-08", "", "报名截止 11月1日，活动于 2026年11月8日 举行。"),
        ("E12 description date == date_end, single day event", "2026-11-08", "", "活动于 11月21日 结束。"),
        ("E13 description has 11月 but no year", "2026-11-08", "", "比赛于 11月8日 举行。"),
        ("E14 description year-only variant", "2026-11-08", "", "活动于 2026/11/08 举行。"),
    ]
    for label, start, end, description in e_cases:
        answers = dict(ANSWERS)
        answers["date_start"] = start
        answers["date_end"] = end
        answers["event_description"] = description
        ok, errors, warnings = form.validate_answers(answers)
        date_warnings = [w for w in warnings if "neither the start nor the end" in w]
        print(f"  {label:52} warned={bool(date_warnings)}")
        if date_warnings:
            print(f"        description: {description!r}")
            print(f"        fields     : start={start!r} end={end!r}")
            print(f"        warning    : {date_warnings[0][:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
