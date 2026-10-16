"""Validator regression tests - no API key, no network.

Locks in both directions of every rule: that real defects are caught, and that the
things the approved corpus tolerates are NOT flagged (a validator that rejects
approved-style copy is worse than none).

    <python> tests/validate_cases.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import validate  # noqa: E402

_MORE = [
    {
        "number": "07",
        "heading_cn": "代表风采",
        "heading_en": "Delegate Voices",
        "body": [
            {"kind": "bilingual",
             "cn": "来自不同国家的代表在会前反复推敲措辞，在会场内外主动寻找共识，把课堂上学到的国际关系理论真正用到了具体的议题讨论之中。",
             "en": "Delegates from different countries refined their wording before the session and looked for common ground throughout."},
        ],
    },
    {
        "number": "08",
        "heading_cn": "组织工作",
        "heading_en": "Organisation",
        "body": [
            {"kind": "bilingual",
             "cn": "从会场布置到议程计时，从文件分发到餐饮安排，志愿者同学们在台前幕后做了大量细致的工作，保障了整个会期的顺畅运转。",
             "en": "From room setup to timekeeping and documents, the volunteers did the detailed work that kept the session running."},
            {"kind": "bilingual",
             "cn": "会务组还提前整理了议事规则手册与常见问题清单，帮助首次参会的同学快速进入状态，也让整个议程的节奏更加紧凑高效。",
             "en": "The organising team also prepared a rules handbook and an FAQ for first-time delegates."},
        ],
    },
]


GOOD: dict = {
    "meta": {"doc_type": "回顾", "slug": "case"},
    "title": {"cn": "国际青年俱乐部 | 活动回顾：APEC智慧校园创新系列", "en": "APEC Smart Campus Review"},
    "lead": {
        "cn": "2026年7月19日至21日，第二届鹏海模拟联合国大会在深圳北理莫斯科大学成功举办，来自各校的代表齐聚一堂，围绕多个国际议题展开思辨与交锋，充分展现了青年学子的学术素养与表达能力。",
        "en": "From July 19 to 21, 2026, the 2nd Penghai Model United Nations Conference was held successfully at SMBU, bringing together delegates from many schools.",
    },
    "sections": [
        {
            "number": "01",
            "heading_cn": "活动背景",
            "heading_en": "Background",
            "body": [
                {
                    "kind": "bilingual",
                    "cn": "本场大会由国际青年俱乐部与鹏海模联组委会合作举办，旨在为国际学生提供锻炼谈判与公共表达的舞台，让同学们在真实的议事规则中理解多边协商的运作方式。",
                    "en": "The conference was co-organised with the Penghai MUN committee to give international students a stage for negotiation and public speaking.",
                },
            ],
        },
        {
            "number": "02",
            "heading_cn": "活动详情",
            "heading_en": "Event Highlights",
            "body": [
                {
                    "kind": "bilingual",
                    "cn": "本次大会设四个会场，议题涵盖1923年鲁尔危机、明金辽东之战以及COP30气候大会等方向，代表们准备充分，在会前便完成了大量资料研读与立场梳理工作。",
                    "en": "The conference featured four committees covering topics from the 1923 Ruhr Crisis to the COP30 climate summit.",
                },
                {
                    "kind": "bilingual",
                    "cn": "在为期三天的议程中，代表们按时提交立场文件，积极参与有主持核心磋商与自由磋商，围绕决议草案的措辞反复打磨，展现出扎实的学术功底与良好的沟通能力。",
                    "en": "Over three days the delegates submitted position papers and took part in moderated and unmoderated caucuses, refining their draft resolutions.",
                },
            ],
        },
        {
            "number": "03",
            "heading_cn": "精彩瞬间",
            "heading_en": "Highlights",
            "body": [
                {
                    "kind": "bilingual",
                    "cn": "会场上，代表们或慷慨陈词，或低声磋商，休息间隙仍在走廊里交换意见。三天会期下来，大家不仅收获了奖项，也结下了跨越国界的友谊。",
                    "en": "On the floor the delegates argued and negotiated, and kept talking in the corridors between sessions.",
                },
                {"kind": "photo_grid", "photos": [{"file": "a.jpg", "caption_cn": "现场", "caption_en": "On site"}]},
            ],
        },
        {
            "number": "04",
            "heading_cn": "获奖名单",
            "heading_en": "Award Winners",
            "body": [
                {
                    "kind": "bilingual",
                    "cn": "经过评委团的严格评审，本届大会的获奖名单如下，恭喜所有获奖代表，也感谢每一位坚持到最后的参会者。",
                    "en": "After careful deliberation by the judging panel, this year's winners are as follows.",
                },
                {
                    "kind": "list",
                    "items": [
                        {"label_cn": "冠军", "label_en": "Champion", "value_cn": "Tugsuu Rentsennatsag"},
                        {"label_cn": "亚军", "label_en": "Runner-up", "value_cn": "Brandon Yunata"},
                    ],
                },
            ],
        },
        {
            "number": "05",
            "heading_cn": "特别感谢",
            "heading_en": "Special Thanks",
            "body": [
                {
                    "kind": "bilingual",
                    "cn": "衷心感谢各位指导老师在筹备与评审期间给予的支持，也感谢志愿者同学在会场布置、代表引导与后勤保障中的默默付出。",
                    "en": "Our sincere thanks to the teachers who supported the preparation and judging, and to the volunteers.",
                },
            ],
        },
        {
            "number": "06",
            "heading_cn": "展望未来",
            "heading_en": "Looking Ahead",
            "body": [
                {
                    "kind": "bilingual",
                    "cn": "感谢每一位参会代表的努力与付出，期待更多国际学子在未来的舞台上继续闪耀，用语言搭建桥梁，用思辨连接世界。",
                    "en": "Thank you to every delegate, and we look forward to seeing more students shine.",
                },
            ],
        },
    ],
    "closing": {
        "heading_cn": "结语",
        "heading_en": "Closing",
        "cn": "感谢每一位参会代表的努力与付出，愿这份荣誉成为新的起点，激励更多国际学子勇敢发声、连接世界。",
        "en": "Thank you to every delegate for their dedication.",
    },
    "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
    "credits": {
        "文字": "Zhumabay Aruzhan",
        "图片": "Yalalt",
        "排版": "Zhumabay Aruzhan",
        "一审": "Samin、柯炽炜",
        "二审": "周宣彤，崔雨旸",
        "三审": "卢锦章",
    },
    "toc": {"previous": "上一篇文章", "next": "下一篇文章"},
    "facts": [{"fact": "2026年7月19日至21日", "source": "brief"}],
    "needs_editor": ["确认获奖者中文姓名"],
}
GOOD["sections"].extend(_MORE)

BRIEF = {
    "event_date": "2026年7月19日至21日",
    # Winners, judges and any figures the article may cite must be in the material:
    # the validator traces every number and name back to the brief and the credits.
    "winners": ["Tugsuu Rentsennatsag", "Brandon Yunata"],
    "topics": "1923年鲁尔危机、明金辽东之战、COP30气候大会",
    "committees": 4,
    "delegates": 30,
    "credits": {"一审": "Samin、柯炽炜", "二审": "周宣彤，崔雨旸", "三审": "卢锦章"},
}

def run(article: dict, **kwargs) -> validate.Report:
    return validate.validate(article, brief=BRIEF, **kwargs)


def expect_codes(report: validate.Report, codes: set[str], label: str, failures: list[str]) -> None:
    found = {f.code for f in report.findings}
    for code in codes:
        if code not in found:
            failures.append(f"{label}: expected {code}, got {sorted(found)}")


def expect_absent(report: validate.Report, codes: set[str], label: str, failures: list[str]) -> None:
    found = {f.code for f in report.findings}
    for code in codes:
        if code in found:
            failures.append(f"{label}: {code} should NOT fire on approved-style copy")


def main() -> int:
    failures: list[str] = []

    # --- baseline: a clean article passes with no errors
    base = run(copy.deepcopy(GOOD))
    if not base.ok:
        failures.append(
            "baseline: expected no errors, got "
            + "; ".join(f"{f.code}: {f.message}" for f in base.errors)
        )
    expect_absent(
        base,
        {"CREDIT-SEPARATOR", "BIL-HEADING", "SIGNOFF-FORM", "FORMAT-HALFWIDTH",
         "FORMAT-QUOTE", "TYPE-PHASE", "BIL-FACT-EN-ONLY", "FACT-NUMBER"},
        "baseline",
        failures,
    )

    # --- credit block: mixed separators are approved, so must not be flagged
    mixed = copy.deepcopy(GOOD)
    mixed["credits"]["一审"] = "Samin, 柯炽炜"
    mixed["credits"]["二审"] = "周宣彤 崔雨旸"
    expect_absent(run(mixed), {"CREDIT-COUNT", "CREDIT-MISSING"}, "mixed separators", failures)

    # --- credit block: a missing role is an error
    missing = copy.deepcopy(GOOD)
    del missing["credits"]["三审"]
    expect_codes(run(missing), {"CREDIT-MISSING"}, "missing 三审", failures)

    # --- credit block: placeholder text is an error
    placeholder = copy.deepcopy(GOOD)
    placeholder["credits"]["二审"] = "待定"
    expect_codes(run(placeholder), {"CREDIT-PLACEHOLDER"}, "placeholder 二审", failures)

    # --- credit block: too many names is a warning
    many = copy.deepcopy(GOOD)
    many["credits"]["三审"] = "卢锦章、甲、乙、丙"
    expect_codes(run(many), {"CREDIT-COUNT"}, "four reviewers", failures)

    # --- bilingual: a CN paragraph with no EN twin is an error
    unpaired = copy.deepcopy(GOOD)
    unpaired["sections"][0]["body"][0].pop("en")
    expect_codes(run(unpaired), {"BIL-PARAGRAPH"}, "unpaired paragraph", failures)

    # --- bilingual: a Chinese-only heading is an error
    cn_only = copy.deepcopy(GOOD)
    cn_only["sections"][1]["heading_en"] = ""
    expect_codes(run(cn_only), {"BIL-HEADING"}, "CN-only heading", failures)

    # --- sign-off must use the official string
    bad_signoff = copy.deepcopy(GOOD)
    bad_signoff["signoff"]["cn"] = "哈工大深圳国际青年俱乐部"
    expect_codes(run(bad_signoff), {"SIGNOFF-FORM"}, "wrong sign-off", failures)

    # --- an invented number must be caught
    invented = copy.deepcopy(GOOD)
    invented["sections"][1]["body"][0]["cn"] = "共有 99 位代表参加本次大会。"
    invented["sections"][1]["body"][0]["en"] = "99 delegates attended."
    expect_codes(run(invented), {"FACT-NUMBER"}, "invented number", failures)

    # --- declaring an invented number in the article's own facts[] must NOT launder it
    laundered = copy.deepcopy(invented)
    laundered["facts"] = [
        {"fact": "2026年7月19日至21日", "source": "brief"},
        {"fact": "共有 99 位代表参加", "source": "STRUCTURED BRIEF"},
    ]
    expect_codes(run(laundered), {"FACT-NUMBER"}, "self-declared number must not whitelist itself", failures)

    # --- a fabricated winner must be caught
    fake_winner = copy.deepcopy(GOOD)
    fake_winner["sections"][3]["body"][1]["items"].append(
        {"label_cn": "特别奖", "label_en": "Special Award", "value_cn": "王梓涵", "value_en": "Wang Zihan"}
    )
    expect_codes(run(fake_winner), {"FACT-NAME"}, "fabricated winner", failures)

    # --- renaming the judge must be caught
    fake_judge = copy.deepcopy(GOOD)
    fake_judge["sections"][0]["body"][0]["cn"] = "本次大会由欧阳明德老师担任评委，代表们准备充分。"
    fake_judge["sections"][0]["body"][0]["en"] = "The conference was judged by Professor Ouyang Mingde."
    expect_codes(run(fake_judge), {"FACT-NAME"}, "fabricated judge", failures)

    # --- real winners from the brief, and the real judge, must NOT be flagged
    expect_absent(run(copy.deepcopy(GOOD)), {"FACT-NAME"}, "real names from the brief", failures)

    # --- ordinary words that start with a surname character are not people
    #     (关注 via 关, 方便 via 方) - a real generation produced both false positives
    ordinary = copy.deepcopy(GOOD)
    ordinary["sections"][0]["body"][0]["cn"] = (
        "国际青年俱乐部关注每一位同学的成长，也方便大家了解活动的安排。"
        "老师与同学们在时间允许的情况下都会参加。"
    )
    ordinary["sections"][0]["body"][0]["en"] = (
        "The club pays attention to every student and makes it easy to follow the schedule."
    )
    expect_absent(run(ordinary), {"FACT-NAME"}, "ordinary words", failures)

    # --- role words after 感谢 are not people. 「感谢指导老师」 was read as a person
    #     called 谢指导, which blocked a perfectly good article on a FACT-NAME error.
    #     The variant WITHOUT 各位 is the one that used to fail; the GOOD fixture
    #     passes only because it happens to say 感谢各位指导老师.
    thankyou = copy.deepcopy(GOOD)
    thankyou["sections"][1]["body"][0]["cn"] = (
        "感谢指导老师对本次会议的精心组织，也感谢评委老师在评审期间的付出。"
    )
    thankyou["sections"][1]["body"][0]["en"] = (
        "Thanks to the guiding teachers for organising the meeting and to the judges."
    )
    expect_absent(run(thankyou), {"FACT-NAME"}, "role words after 感谢", failures)

    # --- and the detector must NOT be blinded by that fix: a fabricated name in the
    #     same shape must still be reported.
    still_caught = copy.deepcopy(GOOD)
    still_caught["sections"][1]["body"][0]["cn"] = "感谢谢昊轩老师对本次会议的精心组织。"
    still_caught["sections"][1]["body"][0]["en"] = "Thanks to Professor Xie Haoxuan."
    expect_codes(run(still_caught), {"FACT-NAME"}, "fabricated name in the same shape", failures)

    # --- a number present in the brief must be accepted
    known = copy.deepcopy(GOOD)
    known["facts"] = [{"fact": "2026年7月19日至21日", "source": "brief"}]
    expect_absent(run(known), {"FACT-NUMBER"}, "brief number", failures)

    # --- knowing a name is not knowing WHERE it belongs. A swapped champion and
    #     runner-up, or a gold medal moved to fourth place, used to pass this check
    #     untouched at 85/100 - and naming the wrong winner is the error most likely
    #     to get an article returned, because the winner reads it.
    ranked = copy.deepcopy(GOOD)
    ranked_brief = copy.deepcopy(BRIEF)
    ranked_brief["winners"] = [
        {"rank_cn": "Champion", "rank_en": "Champion", "names": "Tugsuu Rentsennatsag"},
        {"rank_cn": "Runner-up", "rank_en": "Runner-up", "names": "Brandon Yunata"},
    ]
    expect_absent(validate.validate(ranked, brief=ranked_brief), {"FACT-RANK"},
                  "correct rank attribution", failures)

    swapped = copy.deepcopy(GOOD)
    rows = swapped["sections"][3]["body"][1]["items"]
    rows[0]["value_cn"], rows[1]["value_cn"] = rows[1]["value_cn"], rows[0]["value_cn"]
    expect_codes(validate.validate(swapped, brief=ranked_brief), {"FACT-RANK"},
                 "champion and runner-up swapped", failures)

    # --- the same rule must stay quiet when the brief declares no ranks at all,
    #     which is how the plain-text briefs are written.
    expect_absent(run(copy.deepcopy(GOOD)), {"FACT-RANK"},
                  "an unranked brief cannot contradict anything", failures)

    # --- a fact spelled as a WORD in the brief still whitelists the digit the
    #     article writes. A brief said "a five-minute integral"; the article wrote
    #     "5 分钟" and was reported as an invented number - a blocking error on an
    #     article that contained nothing the operator had not supplied.
    spelled = copy.deepcopy(GOOD)
    spelled_brief = dict(BRIEF)
    spelled_brief["highlights"] = ["One finalist solved a five-minute integral in under 90 seconds"]
    spelled["sections"][0]["body"][0]["cn"] = "决赛中每道题限时 5 分钟，一位选手在 90 秒内完成作答。"
    spelled["sections"][0]["body"][0]["en"] = "Each final problem was limited to 5 minutes."
    expect_absent(validate.validate(spelled, brief=spelled_brief), {"FACT-NUMBER"},
                  "a number spelled as a word in the brief", failures)

    # --- and the same for Chinese numerals in the brief
    cn_spelled = copy.deepcopy(GOOD)
    cn_brief = dict(BRIEF)
    cn_brief["participants_count"] = "三十二名参赛者，四名决赛选手"
    cn_spelled["sections"][0]["body"][0]["cn"] = "共有 32 名参赛者同台竞技，最终 4 位选手晋级决赛。"
    expect_absent(validate.validate(cn_spelled, brief=cn_brief), {"FACT-NUMBER"},
                  "a number spelled as a Chinese numeral in the brief", failures)

    # --- the relaxation must not become a hole: a number in neither spelling is
    #     still an error, even when the brief is full of other numbers.
    still_invented = copy.deepcopy(spelled)
    still_invented["sections"][0]["body"][0]["cn"] = "决赛中每道题限时 777 分钟。"
    expect_codes(validate.validate(still_invented, brief=spelled_brief), {"FACT-NUMBER"},
                 "an invented number alongside word-numbers", failures)


    # --- a fact with no source is an error
    unsourced = copy.deepcopy(GOOD)
    unsourced["facts"] = [{"fact": "某位嘉宾出席", "source": "unknown"}]
    expect_codes(run(unsourced), {"FACT-UNSOURCED"}, "unsourced fact", failures)

    # --- a fact lifted from a previous article is flagged
    leaked = copy.deepcopy(GOOD)
    leaked["facts"] = [{"fact": "32 名参赛者", "source": "corpus:some-old-article"}]
    expect_codes(run(leaked), {"FACT-CORPUS-LEAK"}, "corpus-sourced fact", failures)

    # --- half-width punctuation inside Chinese copy
    halfwidth = copy.deepcopy(GOOD)
    halfwidth["sections"][1]["body"][0]["cn"] = "代表们准备充分,沟通能力突出。"
    expect_codes(run(halfwidth), {"FORMAT-HALFWIDTH"}, "half-width comma", failures)

    # --- approved forms must NOT be flagged: clock ranges, ratios, room numbers
    time_forms = copy.deepcopy(GOOD)
    time_forms["sections"][1]["body"][0]["cn"] = (
        "活动于2026年12月5日（周六）18:30至21:00在哈工大（深圳）A509教室举行，"
        "预赛采用1v1赛制，每场限时5分钟，现场共有120名观众。"
    )
    time_forms["sections"][1]["body"][0]["en"] = (
        "The event ran from 18:30 to 21:00 in Room A509 with 120 audience members."
    )
    expect_absent(run(time_forms), {"FORMAT-HALFWIDTH"}, "approved clock/ratio forms", failures)

    # --- straight quotes inside Chinese copy
    straight = copy.deepcopy(GOOD)
    straight["sections"][1]["body"][0]["cn"] = '本次比赛以"合作"为主题。'
    expect_codes(run(straight), {"FORMAT-QUOTE"}, "straight quotes", failures)

    # --- Chinese characters inside an English field
    cjk_en = copy.deepcopy(GOOD)
    cjk_en["sections"][1]["body"][0]["en"] = "Thank you 感谢 to every delegate."
    expect_codes(run(cjk_en), {"FORMAT-CJK-IN-EN"}, "CJK in EN", failures)

    # --- a preview must not use recap language
    preview = copy.deepcopy(GOOD)
    preview["meta"]["doc_type"] = "预告"
    preview["sections"][1]["body"][0]["cn"] = "本次活动已圆满落幕，感谢大家的参与。"
    preview["sections"][1]["body"][0]["en"] = "The event concluded successfully."
    expect_codes(run(preview), {"TYPE-PHASE"}, "preview with recap verb", failures)

    # --- a recap must not use preview language
    recap = copy.deepcopy(GOOD)
    recap["sections"][1]["body"][0]["cn"] = "活动即将启幕，请扫描二维码报名参加。"
    recap["sections"][1]["body"][0]["en"] = "The event is coming soon; please register."
    recap["sections"][2]["body"][0]["cn"] = "期待与大家相见。"
    recap["sections"][2]["body"][0]["en"] = "See you there."
    recap["lead"]["cn"] = "本次活动即将举行。"
    recap["lead"]["en"] = "The event is coming."
    expect_codes(run(recap), {"TYPE-PHASE"}, "recap with preview verb", failures)

    # --- a number only in the English copy is flagged
    en_only = copy.deepcopy(GOOD)
    en_only["sections"][1]["body"][0]["en"] = "A total of 42 delegates attended the conference."
    expect_codes(run(en_only), {"BIL-FACT-EN-ONLY"}, "EN-only number", failures)

    # --- a photo placed in the article that was never uploaded is an error
    #     (the article places a.jpg; the upload list has a different file)
    unknown_photo = copy.deepcopy(GOOD)
    unknown_photo["sections"][2]["body"][1]["photos"][0]["file"] = "ghost.jpg"
    expect_codes(
        run(unknown_photo, expected_photos=["a.jpg", "b.jpg"]),
        {"PHOTO-UNKNOWN", "PHOTO-UNUSED"},
        "photo never uploaded",
        failures,
    )

    # --- every placed photo exists in the upload list: no photo error at all
    expect_absent(
        run(copy.deepcopy(GOOD), expected_photos=["a.jpg"]),
        {"PHOTO-UNKNOWN", "PHOTO-UNUSED", "PHOTO-NONE"},
        "all photos accounted for",
        failures,
    )

    # --- an uploaded photo that is never placed is a warning
    expect_codes(
        run(copy.deepcopy(GOOD), expected_photos=["a.jpg", "c.jpg"]),
        {"PHOTO-UNUSED"},
        "unused upload",
        failures,
    )

    # --- structural minimums
    short = copy.deepcopy(GOOD)
    short["sections"] = short["sections"][:2]
    expect_codes(run(short), {"STRUCT-SECTIONS"}, "too few sections", failures)

    empty = copy.deepcopy(GOOD)
    empty["sections"][0]["body"] = []
    expect_codes(run(empty), {"STRUCT-EMPTY"}, "empty section", failures)

    bad_kind = copy.deepcopy(GOOD)
    bad_kind["sections"][0]["body"][0]["kind"] = "paragraph"
    expect_codes(run(bad_kind), {"SCHEMA-KIND"}, "unknown block kind", failures)

    # --- headline formula
    no_club = copy.deepcopy(GOOD)
    no_club["title"]["cn"] = "活动回顾：APEC智慧校园创新系列"
    expect_codes(run(no_club), {"HEAD-FORMULA"}, "headline without club name", failures)

    # --- rank title missing its English counterpart
    rank = copy.deepcopy(GOOD)
    rank["sections"][3]["body"][1]["items"][0].pop("label_en")
    rank["sections"][3]["body"][1]["items"][1].pop("label_en")
    expect_codes(run(rank), {"BIL-LIST"}, "rank without English", failures)

    # --- corpus similarity: a paragraph copied from an approved article
    copied = copy.deepcopy(GOOD)
    corpus_text = "三场赛事，三种精神：创新、合作、开放。感谢每一位参赛者的热情、才华与投入。"
    copied["sections"][1]["body"][0]["cn"] = corpus_text
    expect_codes(
        run(copied, corpus_texts=[corpus_text], corpus_labels=["old-article"]),
        {"SIMILARITY"},
        "copied paragraph",
        failures,
    )

    # --- report shape
    payload = base.as_dict()
    for key in ("ok", "score", "errors", "warnings", "stats", "findings"):
        if key not in payload:
            failures.append(f"report: missing key {key}")
    if not 0 <= base.score <= 100:
        failures.append(f"report: score out of range ({base.score})")

    if failures:
        print(f"validate_cases: {len(failures)} FAILURE(S)")
        for item in failures:
            print("  -", item)
        return 1
    print("validate_cases: OK - every rule fires on its defect and stays quiet on approved style")
    print(f"  baseline score {base.score}/100, "
          f"{len(base.errors)} error(s), {len(base.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
