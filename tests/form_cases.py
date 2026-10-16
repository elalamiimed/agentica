"""Intake-form tests: the answers must become a brief the generator and check both trust.

The critical property is that whatever the operator types is exactly what the article is
verified against. If a name or number is lost on the way from form to brief, the check
would flag the article for a fact the operator actually supplied.

    <python> tests/form_cases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import form, validate  # noqa: E402

BASE = {
    "event_name_en": "APEC Smart Campus Innovation Series — Future Skills Challenge",
    "event_name_cn": "APEC 智慧校园创新系列 —— 未来技能挑战赛",
    "doc_type": "回顾",
    "date_start": "2026-11-08",
    "time_start": "14:00",
    "time_end": "17:00",
    "venue_en": "Room A509, HITSZ",
    "venue_cn": "哈工大（深圳）A509 教室",
    "organisers": "HITSZ International Youth Club (HSIYC)",
    "co_organisers": "International Education Center\nAcademiaSphere",
    "participants": "32 contestants, 4 finalists, about 80 audience members; the final round used 5 integrals",
    "judges": "凌怡老师 (Professor Ling Yi) — judge of the finals",
    "winners": "Champion — Tugsuu Rentsennatsag\nRunner-up — Brandon Mantovanni Yunata",
    "highlights": "The 1v1 blitz format drew the biggest crowd",
    "credit_writer": "Zhumabay Aruzhan",
    "credit_photo": "Yalalt",
    "credit_layout": "Najmia Popal",
    "credit_review1": "Samin、柯炽炜",
    "credit_review2": "周宣彤、崔雨旸、高容驷",
    "credit_review3": "卢锦章",
}


def check(condition: bool, label: str, failures: list[str]) -> None:
    if not condition:
        failures.append(label)


def main() -> int:
    failures: list[str] = []

    # ---- 1. the schema is complete and self-consistent
    check(len(form.FIELDS) >= 20, "the form should ask a substantial set of questions", failures)
    keys = [f.key for f in form.FIELDS]
    check(len(keys) == len(set(keys)), "duplicate field keys", failures)
    for f in form.FIELDS:
        check(f.group in form.GROUPS, f"field {f.key} has an unknown group {f.group}", failures)
        check(bool(f.label), f"field {f.key} has no label", failures)
    for required in ("event_name_cn", "event_name_en", "doc_type", "date_start", "venue_en",
                     "credit_writer", "credit_photo", "credit_layout",
                     "credit_review1", "credit_review2", "credit_review3"):
        check(required in form.FIELD_MAP, f"expected a '{required}' question", failures)

    # ---- 2. the required questions are the ones that actually matter
    ok, errors, warnings = form.validate_answers(BASE)
    check(ok, f"a fully answered form should be valid, got {errors}", failures)
    check(not warnings, f"a fully answered form should not warn, got {warnings}", failures)

    # ---- 2b. the article-type dropdown shows English labels but stores the Chinese value
    #         the agent works with (the operator must not have to read Chinese to choose)
    doc_field = form.FIELD_MAP["doc_type"]
    check(doc_field.kind == "select", "the article type should be a dropdown", failures)
    choices = doc_field.as_dict()["choices"]
    check(len(choices) == len(form.ARTICLES),
          f"the dropdown should offer {len(form.ARTICLES)} types, got {len(choices)}", failures)
    for choice in choices:
        check(choice["value"] in form.ARTICLES,
              f"dropdown value {choice['value']!r} is not a known article type", failures)
        check(bool(choice["label"]) and choice["label"] != choice["value"],
              f"dropdown option {choice['value']!r} has no English label", failures)
        check(any(ch.isascii() and ch.isalpha() for ch in choice["label"]),
              f"dropdown label for {choice['value']!r} is not in English", failures)
    check(len({c["value"] for c in choices}) == len(choices), "duplicate dropdown values", failures)

    # every offered type must pass validation when chosen
    for choice in choices:
        ok, errors, _ = form.validate_answers(dict(BASE, doc_type=choice["value"]))
        check(ok, f"article type {choice['value']!r} should be accepted, got {errors}", failures)

    missing = form.missing_required({})
    check(len(missing) == sum(1 for f in form.FIELDS if f.required),
          "every required question should be reported when the form is empty", failures)

    # ---- 3. an incomplete form blocks generation, with the labels named
    for drop in ("event_name_cn", "venue_en", "credit_review3"):
        partial = {k: v for k, v in BASE.items() if k != drop}
        ok, errors, _ = form.validate_answers(partial)
        check(not ok, f"dropping {drop} should block generation", failures)
        label = form.FIELD_MAP[drop].label
        check(any(label in e for e in errors), f"the error for {drop} should name its label", failures)

    # ---- 4. impossible dates and times are rejected
    bad_range = dict(BASE, date_start="2026-11-10", date_end="2026-11-08")
    ok, errors, _ = form.validate_answers(bad_range)
    check(not ok and any("before the start date" in e for e in errors),
          "an end date before the start date should be rejected", failures)

    bad_time = dict(BASE, time_start="17:00", time_end="14:00")
    ok, errors, _ = form.validate_answers(bad_time)
    check(not ok and any("before the start time" in e for e in errors),
          "an end time before the start time should be rejected", failures)

    bad_type = dict(BASE, doc_type="公告")
    ok, errors, _ = form.validate_answers(bad_type)
    check(not ok and any("Unknown article type" in e for e in errors),
          "an unknown article type should be rejected", failures)

    # ---- 5. soft omissions warn rather than block
    no_winners = {k: v for k, v in BASE.items() if k != "winners"}
    ok, errors, warnings = form.validate_answers(no_winners)
    check(ok, "no winners should not block a recap", failures)
    check(any("winners" in w.lower() for w in warnings), "no winners should warn for a recap", failures)

    preview = dict(BASE, doc_type="招募")
    preview.pop("contacts", None)
    ok, errors, warnings = form.validate_answers(preview)
    check(ok, "a 招募 without a contact should not block", failures)
    check(any("contact" in w.lower() for w in warnings),
          "a 招募 without a registration link should warn", failures)

    # ---- 6. dates are rendered the way the approved articles write them
    single = form.answers_to_brief(dict(BASE, date_end=""))
    check("2026年11月8日（周日）" in single, f"single date not formatted as the corpus does: {single[:200]}", failures)
    check("14:00-17:00" in single, "the time range should appear in the brief", failures)

    multi = form.answers_to_brief(dict(BASE, date_start="2026-07-19", date_end="2026-07-21", time_start="", time_end=""))
    check("2026年7月19日至21日" in multi, f"multi-day date not formatted as the corpus does: {multi[:200]}", failures)

    # ---- 7. everything the article may cite survives into the brief
    brief = form.answers_to_brief(BASE)
    for value in ("Zhumabay Aruzhan", "Yalalt", "Najmia Popal", "Samin", "周宣彤", "卢锦章",
                  "Tugsuu Rentsennatsag", "Brandon Mantovanni Yunata", "凌怡", "32 contestants",
                  "International Education Center", "AcademiaSphere"):
        check(value in brief, f"'{value}' was lost between the form and the brief", failures)

    # ---- 8. the no-winners case is stated positively, so the model cannot drift
    no_win_brief = form.answers_to_brief(no_winners)
    check("no awards" in no_win_brief.lower() or "none" in no_win_brief.lower(),
          "the brief should state that there were no awards", failures)

    # ---- 9. the credits block maps to the six roles exactly
    credits = form.answers_to_credits(BASE)
    check(set(credits) == set(validate.CREDIT_ROLES),
          f"credits should cover all six roles, got {sorted(credits)}", failures)
    check(credits["三审"] == "卢锦章", "the final approver was not carried over", failures)

    # ---- 10. the structured brief round-trips through JSON (the web form path)
    structured = form.answers_to_structured_brief(BASE)
    check(json.loads(json.dumps(structured, ensure_ascii=False)) == structured,
          "the structured brief must survive a JSON round-trip", failures)
    check(structured.get("from_form") is True, "the structured brief should be marked as form-sourced", failures)
    check(structured.get("credits") == credits, "structured credits differ from the credit mapping", failures)
    check(len(structured.get("winners") or []) == 2, "both winners should be structured", failures)

    # ---- 11. an article built from the form must pass the check
    section_specs = [
        ("活动背景", "Background",
         "本场赛事是 APEC 智慧校园创新系列的第 1 场活动，由哈工大（深圳）国际青年俱乐部（HSIYC）主办，"
         "国际教育中心与 AcademiaSphere 合办。系列赛以亚太共同体的核心理念为线索，本场对应其中的「创新」，"
         "希望把课堂之外的思考带进校园。",
         "The first event of the series, hosted by HSIYC with the International Education Center and AcademiaSphere."),
        ("活动详情", "Event Highlights",
         "预赛采用快节奏的 1v1 赛制，32 名参赛者激烈角逐，最终 4 位选手进入决赛，围绕 5 道积分题展开比拼。"
         "赛制对准确度与速度同时提出要求，选手不仅要比拼计算功底，也要在倒计时中保持稳定的临场心态。",
         "Thirty-two contestants competed in a blitz 1v1 format and four reached the final."),
        ("精彩瞬间", "Highlights",
         "1v1 环节吸引了最多观众围观，现场气氛热烈，不少同学在赛后仍留在场地交流解题思路。"
         "有选手在最后一题选择冒险换元，虽然未能得分，却赢得了全场掌声。",
         "The 1v1 format drew the biggest crowd of the evening."),
        ("获奖名单", "Award Winners",
         "经过评委团的评审，最终名次如下，恭喜所有获奖选手，也感谢每一位坚持到最后的参赛者。"
         "评委在点评中提到，名次之外更重要的是敢于在压力下表达自己的思路。",
         "After the judging panel's review, the final ranking is as follows."),
        ("特别感谢", "Special Thanks",
         "感谢凌怡老师在决赛中担任裁判，并在筹备期间给予指导，也感谢志愿者同学在场地布置、"
         "计时与后勤保障中的默默付出，让整场比赛得以顺畅运转。",
         "Thanks to Professor Ling Yi for judging the finals and advising during preparation."),
        ("组织工作", "Organisation",
         "从赛前报名、题目校对到场次编排，筹备团队用了近三周时间打磨细节。"
         "比赛当天共安排了计时、记分与场地引导三个小组，确保每一轮对决都能按时开始，"
         "也让选手不必为流程分心。",
         "The organising team spent three weeks on registration, proof-reading and scheduling."),
        ("展望未来", "Looking Ahead",
         "感谢每一位参赛者的努力与付出，期待更多国际学子在未来的舞台上继续闪耀，用思辨连接世界。"
         "系列赛的后续两场将围绕「合作」与「开放」展开，欢迎同学们继续关注与参与。"
         "国际青年俱乐部也会持续为国际学生搭建展示与交流的平台，让每一次尝试都被看见。",
         "Thank you to every contestant, and we look forward to more students shining."),
    ]
    sections = []
    for index, (heading_cn, heading_en, cn, en) in enumerate(section_specs, 1):
        sections.append({
            "number": f"{index:02d}",
            "heading_cn": heading_cn,
            "heading_en": heading_en,
            "body": [{"kind": "bilingual", "cn": cn, "en": en}],
        })

    article = {
        "meta": {"doc_type": "回顾", "slug": "form-case"},
        "title": {"cn": "国际青年俱乐部 | 活动回顾：APEC 智慧校园创新系列 —— 未来技能挑战赛",
                  "en": "APEC Smart Campus Innovation Series — Future Skills Challenge"},
        "lead": {"cn": "2026年11月8日（周日）14:00-17:00，APEC 智慧校园创新系列 —— 未来技能挑战赛在哈工大（深圳）A509 教室举行，32 名参赛者参加预赛，现场约 80 名观众。",
                 "en": "On 8 November 2026 the Future Skills Challenge took place in Room A509, HITSZ."},
        "sections": sections,
        "closing": {"heading_cn": "结语", "heading_en": "Closing",
                    "cn": "感谢每一位参赛者的努力与付出，也感谢国际教育中心与 AcademiaSphere 对本次系列赛的支持。"
                          "愿这一晚的思辨与热情，成为更多国际学子走向更大舞台的起点。",
                    "en": "Thank you to every contestant."},
        "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
        "credits": credits,
        "facts": [{"fact": "2026年11月8日", "source": "brief"}],
        "needs_editor": [],
    }
    report = validate.validate(article, brief=structured)
    if report.errors:
        failures.append(
            "an article built from the form should pass the check, got: "
            + "; ".join(f"{f.code}: {f.message}" for f in report.errors)
        )
    check(report.stats["credit_roles_filled"] == 6, "all six credit roles should be filled", failures)

    # ---- 12. the event-description box: one open question, asked first, developed by the agent
    described = dict(BASE, event_description=(
        "The first round of the APEC Smart Campus Innovation Series happened in A509 on "
        "2026-11-08. 57 students signed up and we ran it as a 1v1 blitz. Tugsuu took the "
        "final against Brandon by a single point."
    ))
    story = [g for g in form.field_groups() if g["group"] == form.GROUP_STORY]
    check(len(story) == 1 and len(story[0]["fields"]) == 1,
          "the description should be the only question in its group", failures)
    check(form.GROUPS[0] == form.GROUP_STORY, "the description should be the first question asked", failures)
    desc_field = form.FIELD_MAP["event_description"]
    check(desc_field.kind == "textarea", "the description must be a free-text box", failures)
    check(desc_field.rows >= 6, "the description box should be tall enough to write in", failures)
    check(desc_field.as_dict()["rows"] == desc_field.rows,
          "the box height must reach the page", failures)
    check(not desc_field.required, "the description must stay optional", failures)
    check(bool(desc_field.placeholder) and bool(desc_field.hint),
          "the description box should show an example and an explanation", failures)
    ok, errors, warnings = form.validate_answers(described)
    check(ok, f"a filled description should not block generation, got {errors}", failures)
    check(not warnings, f"a description agreeing with the date fields should not warn, got {warnings}", failures)

    # it must survive into both the text brief and the structured brief - that is what makes
    # it authoritative material rather than decoration
    described_brief = form.answers_to_brief(described)
    check("57 students signed up" in described_brief,
          "the description was lost between the form and the brief", failures)
    check("EVENT DESCRIPTION" in described_brief,
          "the brief should label the description so the model develops it", failures)
    described_structured = form.answers_to_structured_brief(described)
    check(described_structured.get("event_description", "").startswith("The first round"),
          "the structured brief should carry the description", failures)

    # ---- 13. a fact that appears only in the description is allowed into the article,
    #          and one that appears nowhere is still refused. This is the whole point of
    #          the box: the operator's own words are material, invented words are not.
    import copy  # noqa: PLC0415

    brief_plain = dict(structured)
    brief_plain["raw_notes"] = form.answers_to_brief(BASE)
    brief_described = dict(described_structured)
    brief_described["raw_notes"] = described_brief

    with_57 = copy.deepcopy(article)
    with_57["sections"][2]["body"][0]["cn"] += "本次共有 57 名同学报名参赛。"
    flagged = validate.validate(copy.deepcopy(with_57), brief=brief_plain)
    check(any(f.code == "FACT-NUMBER" and "57" in f.message for f in flagged.errors),
          "a number that appears in no answer at all should still be an error", failures)
    allowed = validate.validate(copy.deepcopy(with_57), brief=brief_described)
    check(not any(f.code == "FACT-NUMBER" and "57" in f.message for f in allowed.errors),
          "a number the operator wrote in the description must not be flagged", failures)

    # ---- 14. a description that contradicts the date fields warns before anything is spent
    stray_date = dict(BASE, event_description="The finals ran on 2026年11月9日 in A509.")
    ok, errors, warnings = form.validate_answers(stray_date)
    check(ok, "a mismatched date in the description should warn, not block", failures)
    check(any("2026-11-09" in w for w in warnings),
          f"a date in the description that is not the event date should warn, got {warnings}", failures)
    agreeing = dict(BASE, event_description="The finals ran on 2026年11月8日 in A509, 14:00-17:00.")
    ok, errors, warnings = form.validate_answers(agreeing)
    check(not warnings, f"a description repeating the event date should not warn, got {warnings}", failures)
    span = dict(BASE, date_end="2026-11-10", event_description="Three days: 2026-11-08 to 2026-11-10.")
    ok, errors, warnings = form.validate_answers(span)
    check(not any("2026-1" in w for w in warnings),
          f"both ends of a multi-day event should be accepted, got {warnings}", failures)

    # Notes usually omit the year, and "11月9日" is as much a date as "2026年11月9日".
    short_ok = dict(BASE, event_description="活动于 11月8日（周日）14:00 在 A509 举行。")
    ok, errors, warnings = form.validate_answers(short_ok)
    check(not warnings, f"a year-less date matching the event date should not warn, got {warnings}", failures)
    short_bad = dict(BASE, event_description="活动于 11月9日 在 A509 举行。")
    ok, errors, warnings = form.validate_answers(short_bad)
    check(any("11-09" in w for w in warnings),
          f"a year-less date that differs from the event date should warn, got {warnings}", failures)
    # A deadline is a legitimate second date: it warns, it must not block.
    deadline = dict(BASE, event_description="活动于 11月8日 举行，报名截止 11月1日。")
    ok, errors, warnings = form.validate_answers(deadline)
    check(ok, "a description with a second deadline must still be submittable", failures)
    check(any("11-01" in w for w in warnings), "the deadline should be named in the warning", failures)

    # "march" is a verb before it is a month: an ordinary sentence must not be read as a date.
    marching = dict(BASE, event_description="The students march 5 kilometres along the coast.")
    ok, errors, warnings = form.validate_answers(marching)
    check(not warnings, f"'march 5 kilometres' is not a date and must not warn, got {warnings}", failures)
    # Two days of a multi-day event are both dates.
    two_days = dict(BASE, date_end="2026-11-09", event_description="活动于 11月8日至9日 举行。")
    ok, errors, warnings = form.validate_answers(two_days)
    check(not warnings, f"a range matching both declared dates must not warn, got {warnings}", failures)
    # An impossible date is not silently accepted as "a different date".
    impossible = dict(BASE, event_description="活动于 2026年2月30日 举行。")
    ok, errors, warnings = form.validate_answers(impossible)
    check(not any("02-30" in w for w in warnings),
          f"an impossible date should not be reported as a different date, got {warnings}", failures)

    if failures:
        print(f"form_cases: {len(failures)} FAILURE(S)")
        for item in failures:
            print("  -", item)
        return 1
    print("form_cases: OK - the answers become a brief the generator and the check both trust")
    print(f"  {len(form.FIELDS)} questions in {len(form.GROUPS)} groups, "
          f"{sum(1 for f in form.FIELDS if f.required)} required")
    print(f"  an article built from a filled form scores {report.score}/100 with {len(report.errors)} error(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
