"""The intake form: the exact questions the operator answers, in English.

The form is not decoration. Each field exists because the approved articles always
carry that fact, or because the pre-submission check refuses to guess it:

* **Date / venue / participants** appear in the lead of every approved article.
* **Winners and judges** are the highest-risk facts. The check blocks a person who is
  named in the article but absent from the material, so the operator must supply them.
  Leaving "Award winners" blank is what tells the agent "this event has no winners".
* **The six credit roles** are the top rejection cause. Only 卢锦章 as final approver is
  stable across the corpus; the rest of the roster rotates weekly, so it is asked for
  every time and never inferred.
* **Previous / next titles** feed the 精彩回顾 · Table of Contents card.
* **The event description** is the one open question. The operator writes what happened in
  their own words - rough notes, either language, as short or as long as they like - and the
  agent develops it into the article's lead and body prose. It is asked first because it is
  the material everything else annotates, and because anything a writer mentions in it is
  material the article is then allowed to use.

The answers are assembled into a brief that the generator and the check both consume, so
what the operator typed is exactly what the article is verified against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .validate import CREDIT_ROLES, canonical_dates

ARTICLES = ("回顾", "预告", "招募", "收官", "喜报", "竞赛", "活动")

# The article type is stored in Chinese (it drives the model's tense and the checks),
# but the operator picks it from an English label. The Chinese is shown alongside so a
# member who knows the house terms can still recognise them.
ARTICLE_CHOICES: tuple[tuple[str, str], ...] = (
    ("回顾", "Recap — an event that already happened"),
    ("预告", "Preview — an upcoming event"),
    ("招募", "Recruitment — calling for participants"),
    ("收官", "Series finale — the last event of a series"),
    ("喜报", "Good news — an award or achievement"),
    ("竞赛", "Competition — rules or a competition post"),
    ("活动", "General event article"),
)


def choice_label(value: str, label: str) -> str:
    """The bilingual option text shown in the dropdown and the CLI: English (中文)."""
    return label if not value or value in label else f"{label} ({value})"

# Colour-coded groups so the page can render a long form in readable sections.
# "Event story" comes first: it is the one question that lets the operator write freely,
# and it is the material the article is actually built from.
GROUP_STORY = "Event story"
GROUP_BASICS = "Event basics"
GROUP_PEOPLE = "People"
GROUP_RESULTS = "Results"
GROUP_ARTICLE = "Article structure"
GROUP_CREDITS = "Review credits (三审)"
GROUPS = (GROUP_STORY, GROUP_BASICS, GROUP_PEOPLE, GROUP_RESULTS, GROUP_ARTICLE, GROUP_CREDITS)


@dataclass
class Field:
    """One question on the form."""

    key: str
    label: str
    group: str
    hint: str = ""
    placeholder: str = ""
    kind: str = "text"        # text | textarea | date | time | select
    options: tuple[str, ...] = ()
    choices: tuple[tuple[str, str], ...] = ()   # (value, label) pairs for a select
    required: bool = False
    bilingual: bool = False    # offers a second input for the Chinese form of the value
    rows: int = 0              # textarea height in lines (0 = the page default)

    def as_dict(self) -> dict:
        choices = [
            {"value": v, "label": choice_label(v, lbl)} for v, lbl in self.choices
        ]
        if not choices and self.options:
            choices = [{"value": o, "label": o} for o in self.options]
        return {
            "key": self.key,
            "label": self.label,
            "group": self.group,
            "hint": self.hint,
            "placeholder": self.placeholder,
            "kind": self.kind,
            "options": list(self.options),
            "choices": choices,
            "required": self.required,
            "bilingual": self.bilingual,
            "rows": self.rows,
        }


FIELDS: tuple[Field, ...] = (
    # ----------------------------------------------------------------- event story
    Field("event_description", "Describe the event in your own words", GROUP_STORY,
          kind="textarea", rows=9,
          placeholder="Rough notes are fine — two lines or two paragraphs, in English or in "
                      "Chinese (or a mix).\n\n"
                      "e.g. The first round of the APEC Future Skills Challenge finally happened in "
                      "A509 on 8 November. 32 students from 7 countries signed up and we ran it as a "
                      "1v1 blitz: two people at the whiteboard, five integrals, 90 seconds each. The "
                      "room was packed — about 80 people stayed to the end. Tugsuu took the final "
                      "against Brandon by one point. 凌怡老师 judged and gave feedback afterwards.",
          hint="Agentica develops this into the article: it orders the story, writes it out as full "
               "bilingual prose and keeps every fact you mention — and it may not add facts you did "
               "not supply here or in the fields below. Press “Develop this description” to have "
               "Agentica improve it first; the result lands back in this box for you to edit."),
    # ---------------------------------------------------------------- event basics
    Field("event_name_en", "Event name (English)", GROUP_BASICS, required=True,
          placeholder="APEC Smart Campus Innovation Series — Future Skills Challenge",
          hint="The English name as it should appear in the article."),
    Field("event_name_cn", "Event name (Chinese)", GROUP_BASICS, required=True,
          placeholder="APEC 智慧校园创新系列 —— 未来技能挑战赛",
          hint="Used in the Chinese headline and body. Ask a colleague if you are unsure."),
    Field("doc_type", "What kind of article is this?", GROUP_BASICS, kind="select",
          choices=ARTICLE_CHOICES, required=True,
          hint="This decides the article's tense and framing: a recap speaks in the past "
               "(圆满落幕), a preview in the future (即将启幕)."),
    Field("date_start", "Date the event takes place", GROUP_BASICS, kind="date", required=True,
          hint="A single-day event needs only this. A future event is normal for 预告 / 招募."),
    Field("date_end", "Last day (only if it runs over several days)", GROUP_BASICS, kind="date"),
    Field("time_start", "Start time", GROUP_BASICS, kind="time"),
    Field("time_end", "End time", GROUP_BASICS, kind="time"),
    Field("venue_en", "Venue (English)", GROUP_BASICS, required=True,
          placeholder="Room A509, HITSZ", hint="Building and room number if there is one."),
    Field("venue_cn", "Venue (Chinese)", GROUP_BASICS,
          placeholder="哈工大（深圳）A509 教室"),
    Field("organisers", "Who organised it?", GROUP_BASICS, kind="textarea",
          placeholder="HITSZ International Youth Club (HSIYC)",
          hint="One per line. The club is added automatically if you leave this blank."),
    Field("co_organisers", "Co-organisers / partners / sponsors", GROUP_BASICS, kind="textarea",
          placeholder="International Education Center\nAcademiaSphere",
          hint="One per line. Only list partners who should be credited publicly."),
    Field("participants", "Who took part, and how many?", GROUP_BASICS, kind="textarea",
          placeholder="32 contestants, 4 finalists, about 80 audience members",
          hint="Numbers must be exact — the check flags any figure it cannot find here."),

    # ---------------------------------------------------------------------- people
    Field("judges", "Judges, speakers or guests", GROUP_PEOPLE, kind="textarea",
          placeholder="凌怡老师 (Professor Ling Yi) — judge of the finals",
          hint="One per line, with their role and title. These names are checked against your "
               "answers, so a name typed here is a name the article is allowed to use."),
    Field("winners", "Award winners", GROUP_PEOPLE, kind="textarea",
          placeholder="Champion — Tugsuu Rentsennatsag\nRunner-up — Brandon Mantovanni Yunata",
          hint="One per line as «award — name». Leave blank if the event had no winners or "
               "awards; the agent will not invent any."),
    Field("contacts", "Contact or registration link", GROUP_PEOPLE, kind="textarea",
          placeholder="iyc.hitsz@outlook.com\nhttps://mp.weixin.qq.com/s/...",
          hint="Required for 预告 and 招募: readers need to know how to take part."),

    # --------------------------------------------------------------------- results
    Field("highlights", "Anything memorable you want in the article", GROUP_RESULTS, kind="textarea",
          placeholder="The 1v1 blitz format drew the biggest crowd\nA delegate solved a five-minute "
                      "integral in under 90 seconds",
          hint="One per line. This is where the article gets its colour — the agent will not "
               "make things up on its own."),
    Field("results_summary", "Outcome or result summary", GROUP_RESULTS, kind="textarea",
          placeholder="All three APEC competitions closed successfully; two delegates qualified "
                      "for the regional round.",
          hint="Useful for 回顾 and 收官. Leave blank if there is nothing to report."),

    # -------------------------------------------------------------- article structure
    Field("programme", "Programme or series this belongs to", GROUP_ARTICLE,
          placeholder="APEC Smart Campus Innovation Series"),
    Field("toc_previous", "Title of the previous article in the series", GROUP_ARTICLE,
          placeholder="国际青年俱乐部 | APEC智慧校园创新系列竞赛",
          hint="Shown in the 精彩回顾 · Table of Contents card. Leave blank to omit the card."),
    Field("toc_next", "Title of the next article", GROUP_ARTICLE,
          placeholder="扬帆启新程，筑梦向未来 | 2026级国际新生入学教育",
          hint="Can stay blank if the next article is not published yet."),

    # --------------------------------------------------------------------- credits
    Field("credit_writer", "Text (文字)", GROUP_CREDITS, required=True,
          placeholder="Zhumabay Aruzhan", hint="Who wrote the copy."),
    Field("credit_photo", "Photos (图片)", GROUP_CREDITS, required=True,
          placeholder="Yalalt", hint="Who took or supplied the photos."),
    Field("credit_layout", "Layout (排版)", GROUP_CREDITS, required=True,
          placeholder="Najmia Popal", hint="Who did the layout."),
    Field("credit_review1", "First review (一审)", GROUP_CREDITS, required=True,
          placeholder="Samin、柯炽炜",
          hint="1-3 names. Copy this from the current roster — it changes weekly and the "
               "agent will never guess it."),
    Field("credit_review2", "Second review (二审)", GROUP_CREDITS, required=True,
          placeholder="周宣彤、崔雨旸、高容驷", hint="1-3 names."),
    Field("credit_review3", "Final approval (三审)", GROUP_CREDITS, required=True,
          placeholder="卢锦章", hint="1-2 names. 卢锦章 holds this role in 16 of the 17 approved articles."),
)

FIELD_MAP: dict[str, Field] = {f.key: f for f in FIELDS}

# Keys the browser submits but which are not article material.
NON_BRIEF_KEYS = frozenset({"repair_rounds", "doc_type"})


def field_groups() -> list[dict]:
    """The form definition the page renders: groups, each with its fields in order."""
    return [
        {"group": group, "fields": [f.as_dict() for f in FIELDS if f.group == group]}
        for group in GROUPS
    ]


def missing_required(answers: dict) -> list[str]:
    """Labels of the required questions still unanswered."""
    return [
        f.label
        for f in FIELDS
        if f.required and not str(answers.get(f.key) or "").strip()
    ]


def _lines(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip(" •-\t") for line in text.split("\n") if line.strip(" •-\t")]


def _join(value: Any, sep: str = "、") -> str:
    return sep.join(_lines(value))


def format_date(answers: dict) -> str:
    """Render the date the way the approved articles do: 2026年11月8日 / 2026年11月8日至21日.

    The browser's date input gives ``2026-11-08``; the corpus writes dates in Chinese,
    so convert rather than passing the ISO form into the prose.
    """
    start = _chinese_date(str(answers.get("date_start") or "").strip())
    end = _chinese_date(str(answers.get("date_end") or "").strip())
    if not start:
        return ""
    if end and end != start:
        # The corpus writes a range as 2026年7月19日至21日 - repeat only the day when the
        # month and year are the same, otherwise give the full end date.
        same_month = (
            start.count("年") == 1 and end.count("年") == 1
            and start.split("年")[0] == end.split("年")[0]
            and start.split("年")[1].split("月")[0] == end.split("年")[1].split("月")[0]
        )
        if same_month and "月" in end:
            return f"{start}至{end.split('月')[1]}"
        return f"{start}至{end}"
    return start


def _chinese_date(value: str) -> str:
    """``2026-11-08`` -> ``2026年11月8日``; anything else is passed through unchanged."""
    if not value:
        return ""
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if not match:
        return value
    year, month, day = (int(g) for g in match.groups())
    return f"{year}年{month}月{day}日"


def chinese_weekday(value: str) -> str:
    """``2026-11-08`` -> ``周日``, for the (周六) the approved articles add to dates."""
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value or "")
    if not match:
        return ""
    year, month, day = (int(g) for g in match.groups())
    try:
        weekday = datetime(year, month, day).weekday()
    except ValueError:
        return ""
    return f"（{WEEKDAYS_CN[weekday]}）"


WEEKDAYS_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def format_time(answers: dict) -> str:
    start = str(answers.get("time_start") or "").strip()
    end = str(answers.get("time_end") or "").strip()
    if start and end:
        return f"{start}-{end}"
    return start or end


def answers_to_brief(answers: dict) -> str:
    """Turn the form answers into a brief for the generator and the validator.

    The wording is deliberately field-labelled: the brief is both the model's source
    material and the whitelist the fact checks run against.
    """
    event_cn = str(answers.get("event_name_cn") or "").strip()
    event_en = str(answers.get("event_name_en") or "").strip()
    lines: list[str] = ["EVENT", "-----"]

    if event_cn and event_en and event_cn != event_en:
        lines.append(f"Event name: {event_cn} / {event_en}")
    else:
        lines.append(f"Event name: {event_cn or event_en}")

    doc_type = str(answers.get("doc_type") or "").strip()
    if doc_type:
        lines.append(f"Article type: {doc_type}")

    date = format_date(answers)
    when = format_time(answers)
    if date:
        # The approved articles often add the weekday: 2026年11月8日（周六）14:00-17:00
        weekday = chinese_weekday(str(answers.get("date_start") or ""))
        if weekday and "至" not in date:
            date = date.replace("日", f"日{weekday}", 1)
        lines.append(f"Date: {date}" + (f" {when}" if when else ""))
    elif when:
        lines.append(f"Time: {when}")

    venue_cn = str(answers.get("venue_cn") or "").strip()
    venue_en = str(answers.get("venue_en") or "").strip()
    if venue_cn and venue_en and venue_cn != venue_en:
        lines.append(f"Venue: {venue_cn} / {venue_en}")
    elif venue_cn or venue_en:
        lines.append(f"Venue: {venue_cn or venue_en}")

    club = "哈工大（深圳）国际青年俱乐部（HSIYC）"
    organisers = _lines(answers.get("organisers")) or [club]
    lines.append("Organisers: " + _join(organisers))
    co = _lines(answers.get("co_organisers"))
    if co:
        lines.append("Co-organisers / partners: " + _join(co))

    participants = str(answers.get("participants") or "").strip()
    if participants:
        lines.append(f"Participants: {participants}")

    programme = str(answers.get("programme") or "").strip()
    if programme:
        lines.append(f"Programme: {programme}")

    description = str(answers.get("event_description") or "").strip()
    if description:
        lines.append("")
        lines.append("EVENT DESCRIPTION (the club's own words — develop this into the article)")
        lines.append("-----")
        lines.extend(f"  {line.strip()}" for line in description.splitlines() if line.strip())

    for key, label in (
        ("judges", "Judges / speakers / guests"),
        ("winners", "Award winners"),
        ("highlights", "Highlights to include"),
        ("results_summary", "Result summary"),
        ("contacts", "Contact / registration"),
    ):
        values = _lines(answers.get(key))
        if values:
            lines.append("")
            lines.append(f"{label}:")
            lines.extend(f"  - {v}" for v in values)

    if not _lines(answers.get("winners")):
        lines.append("")
        lines.append("Award winners: none — this event had no awards. Do not invent any.")

    toc_prev = str(answers.get("toc_previous") or "").strip()
    toc_next = str(answers.get("toc_next") or "").strip()
    if toc_prev or toc_next:
        lines.append("")
        lines.append("Table of Contents card:")
        lines.append(f"  Previous: {toc_prev or '(blank)'}")
        lines.append(f"  Next: {toc_next or '(blank)'}")

    lines.append("")
    lines.append("REVIEW CREDITS (三审 block — copy exactly, never change a name)")
    lines.append("-----")
    for role, key in zip(CREDIT_ROLES, CREDIT_KEYS):
        value = str(answers.get(key) or "").strip()
        if value:
            lines.append(f"{role} | {value}")

    return "\n".join(lines).strip() + "\n"


CREDIT_KEYS = (
    "credit_writer",
    "credit_photo",
    "credit_layout",
    "credit_review1",
    "credit_review2",
    "credit_review3",
)


def answers_to_credits(answers: dict) -> dict[str, str]:
    """The 三审 block as structured data, for the validator and the renderers."""
    out: dict[str, str] = {}
    for role, key in zip(CREDIT_ROLES, CREDIT_KEYS):
        value = _join(answers.get(key))
        if value:
            out[role] = value
    return out


def answers_to_structured_brief(answers: dict) -> dict:
    """A pre-filled structured brief.

    The brief-normalising LLM call exists to turn messy prose into fields. When the
    operator fills in the form there is nothing to normalise, so this supplies the
    structure directly - one fewer API call, and no chance of the model reinterpreting
    a date or a name on the way in.
    """
    winners = []
    for line in _lines(answers.get("winners")):
        # "Champion — Tugsuu Rentsennatsag" / "冠军：Tugsuu Rentsennatsag"
        parts = line.replace("—", "-").replace("：", ":").split(" - ", 1)
        if len(parts) == 2:
            label, name = parts[0].strip(), parts[1].strip()
        elif ":" in line:
            label, name = (p.strip() for p in line.split(":", 1))
        else:
            label, name = "", line
        winners.append({"rank_cn": label, "rank_en": label, "names": name})

    return {
        "doc_type": str(answers.get("doc_type") or ""),
        "event_description": str(answers.get("event_description") or "").strip(),
        "title_cn": str(answers.get("event_name_cn") or ""),
        "title_en": str(answers.get("event_name_en") or ""),
        "event_date": format_date(answers),
        "event_time": format_time(answers),
        "venue": str(answers.get("venue_cn") or answers.get("venue_en") or ""),
        "venue_en": str(answers.get("venue_en") or ""),
        "organisers": _lines(answers.get("organisers")) or ["哈工大（深圳）国际青年俱乐部（HSIYC）"],
        "partners": _lines(answers.get("co_organisers")),
        "participants_count": str(answers.get("participants") or ""),
        "judges": _lines(answers.get("judges")),
        "winners": winners,
        "programme": str(answers.get("programme") or ""),
        "highlights": _lines(answers.get("highlights")),
        "results_summary": str(answers.get("results_summary") or ""),
        "contacts": _lines(answers.get("contacts")),
        "credits": answers_to_credits(answers),
        "toc": {
            "previous": str(answers.get("toc_previous") or ""),
            "next": str(answers.get("toc_next") or ""),
        },
        "photo_notes": [],
        "missing": [],
        "from_form": True,
    }


def validate_answers(answers: dict) -> tuple[bool, list[str], list[str]]:
    """Check the form before spending tokens.

    Returns ``(ok, errors, warnings)``. Errors block generation; warnings are things the
    operator may legitimately leave out (a contact link for a recap, for instance).
    """
    errors: list[str] = []
    warnings: list[str] = []

    missing = missing_required(answers)
    if missing:
        errors.append("Required questions unanswered: " + "; ".join(missing))

    doc_type = str(answers.get("doc_type") or "").strip()
    if doc_type and doc_type not in ARTICLES:
        errors.append(f"Unknown article type '{doc_type}'. Choose one of: {', '.join(ARTICLES)}")

    if not _lines(answers.get("winners")) and doc_type in ("回顾", "收官", "喜报", "竞赛"):
        warnings.append(
            "No award winners listed. If this event had prizes, add them — the agent will not invent any."
        )
    if doc_type in ("预告", "招募") and not _lines(answers.get("contacts")):
        warnings.append(
            "No contact or registration link given. A 预告 / 招募 normally tells readers how to take part."
        )

    date_start = str(answers.get("date_start") or "").strip()
    date_end = str(answers.get("date_end") or "").strip()
    if date_start and date_end and date_end < date_start:
        errors.append(f"The end date ({date_end}) is before the start date ({date_start}).")

    start = str(answers.get("time_start") or "").strip()
    end = str(answers.get("time_end") or "").strip()
    if start and end and end < start and len(start) == 5 and len(end) == 5:
        errors.append(f"The end time ({end}) is before the start time ({start}).")

    venue = str(answers.get("venue_en") or answers.get("venue_cn") or "").strip()
    if venue and len(venue) < 3:
        warnings.append(f"Venue '{venue}' looks too short to be a real place.")

    # The description is the one free-text answer, and it is authoritative material: a date
    # written in it is allowed into the article. So a date that disagrees with the date
    # fields is worth saying out loud before generation, not after - a recap published on
    # the wrong day is a guaranteed correction.
    description = str(answers.get("event_description") or "")
    if description:
        declared_full: set[str] = set()
        declared_days: set[str] = set()
        for value in (date_start, date_end):
            if not value:
                continue
            declared_full.add(value)
            for found in canonical_dates(value)[0]:
                declared_full.add(found)
                declared_days.add(found[-5:])
        stray = []
        for found in sorted(canonical_dates(description)[0]):
            # A date with a year must match the declared date exactly; a date without one
            # only has a month and a day to compare.
            known = found in declared_full if len(found) == 10 else found[-5:] in declared_days
            if not known:
                stray.append(found)
        if stray:
            warnings.append(
                "The description mentions " + "、".join(stray)
                + ", which is neither the start nor the end date you gave. If that is a "
                  "different deadline or session, ignore this; if it is a typo, fix it - the "
                  "article may only cite dates you supplied."
            )

    return (not errors), errors, warnings
