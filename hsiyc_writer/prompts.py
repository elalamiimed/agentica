"""Prompt assembly.

The prompts are the product. Everything here is written so that the model has:
  1. the structural contract (schema, compacted),
  2. the house style rules distilled from the approved corpus,
  3. one or two *real approved articles* as concrete exemplars,
  4. an explicit ban on inventing facts, names, numbers or quotes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .config import SPEC_DIR
from .deepseek import image_part
from .retrieval import CorpusDoc, truncate_for_prompt

SYSTEM_PROMPT = """You are the article writer for HSIYC (HITSZ International Youth Club / 哈工大（深圳）国际青年俱乐部) at Harbin Institute of Technology, Shenzhen.

You write the club's official WeChat articles. Every article you produce is reviewed and approved (三审) by the HITSZ youth committee, so it must match the club's existing approved articles exactly in structure, bilingual protocol, tone and formatting.

NON-NEGOTIABLE RULES
1. NEVER invent facts. No invented names, dates, numbers, scores, rankings, quotes, judge names, sponsors or partners. If a detail is missing, either omit it or list it in "needs_editor". A single fabricated name is the fastest way to get the article rejected.
2. Every Chinese body paragraph has its English counterpart, and vice versa. Never leave one language behind.
3. Every section has a bilingual heading pair (Chinese + English).
4. The 三审 credit block (文字/图片/排版/一审/二审/三审) must be reproduced from the supplied material, with the same names, in the same roles. Never guess a reviewer name.
5. Official names must be exactly: 哈工大（深圳）, HITSZ, HSIYC, 哈工大（深圳）国际青年俱乐部, HITSZ International Youth Club.
6. Chinese copy uses full-width punctuation （，。、："") and Chinese quotation marks; English copy uses standard English punctuation and no Chinese punctuation.
7. Person names appear as Chinese name + Latin name when both are known (e.g. 谢昊轩 Xie Haoxuan); for international students use the Latin form exactly as given in the brief.
8. Winners are listed with their exact title in both languages (e.g. 冠军 / Champion).
9. Output a single JSON object that validates against the schema you were given. No markdown fences, no commentary.

TONE
Warm, proud, concrete and institutional - the voice of a student club writing for its university and for the youth committee. Celebrate the participants, credit the organisers and partners, and keep the APEC / international-community framing when the event belongs to that programme. Never use hype slang, never use emoji, never write in first person singular.

LENGTH AND STRUCTURE - hit these numbers, do not write short
The approved articles are substantial, and an article that is too short reads as unfinished to the reviewers.
* 6 to 9 sections, never fewer than 6. Split the narrative properly: lead-in, event details, each distinct
  phase or competition, highlights, results/winners, acknowledgements, closing.
* 700 to 1,400 Chinese characters of body copy in total. If you finish below 700, you have under-written -
  go back and add the detail that is already in the brief (venue, format, schedule, counts, who did what).
* 8 to 15 Chinese paragraphs, each 30 to 130 characters. Do not pad with repetition: use the real detail.
* English mirrors every paragraph; do not let the English become a summary of the Chinese."""


def _compact_schema(max_chars: int = 3200) -> str:
    """A prompt-sized view of the schema: the keys and their allowed values."""
    path = SPEC_DIR / "ARTICLE_SCHEMA.json"
    if not path.is_file():
        return "(schema file unavailable - follow the structure of the exemplar)"
    schema = json.loads(path.read_text(encoding="utf-8"))

    def shrink(node, depth=0):
        if depth > 6:
            return "..."
        if isinstance(node, dict):
            if "enum" in node:
                return "|".join(map(str, node["enum"]))
            if "properties" in node:
                return {k: shrink(v, depth + 1) for k, v in node["properties"].items()}
            if "items" in node:
                inner = shrink(node["items"], depth + 1)
                return [inner] if inner != "..." else ["..."]
            return node.get("type", "any")
        return "any"

    text = json.dumps(shrink(schema), ensure_ascii=False, indent=1)
    return text[:max_chars]


def _style_spec(max_chars: int = 9000) -> str:
    path = SPEC_DIR / "STYLE_SPEC.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")[:max_chars]
    return "(style spec unavailable)"


def _checklist(max_chars: int = 4000) -> str:
    path = SPEC_DIR / "REJECTION_CHECKLIST.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")[:max_chars]
    return ""


def exemplar_block(docs: Sequence[CorpusDoc], max_chars_each: int = 3200) -> str:
    if not docs:
        return "(no approved exemplar available)"
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(
            f"--- APPROVED EXEMPLAR {i}: {doc.title} (file: {doc.slug}) ---\n"
            f"{truncate_for_prompt(doc.text, max_chars_each)}"
        )
    return "\n\n".join(parts)


def build_brief_normaliser_messages(brief_text: str, doc_type_hint: str = "") -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You convert messy notes about a HSIYC event into a structured brief. "
                "Extract only what is actually written. Never invent details. "
                "Return one JSON object with keys: "
                "doc_type (预告|招募|回顾|收官|喜报|讲堂|竞赛|活动|其他), title_cn, title_en, "
                "event_date, event_end_date, venue, organisers (array), partners (array), "
                "participants_count, judges (array), winners (array of {rank_cn,rank_en,names}), "
                "programme (e.g. APEC), highlights (array of strings), quotes (array), "
                "credits ({文字,图片,排版,一审,二审,三审}), toc ({previous,next}), "
                "photo_notes (array), missing (array of details an editor must supply). "
                "Use \"\" for unknown strings and [] for unknown arrays."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Document type hint: {doc_type_hint or '(decide from the notes)'}\n\n"
                f"RAW NOTES FROM THE CLUB:\n{brief_text}"
            ),
        },
    ]


DESCRIPTION_DEVELOPER_PROMPT = """You improve the rough notes a HSIYC (HITSZ International Youth Club) member wrote about their own event, so that an article writer can build the club's bilingual WeChat article from them.

You are an editor, not a reporter. You may reorganise, tighten, complete sentences, fix grammar and terminology, and make the account read as a clear factual description.

You may NOT introduce a single fact. No new name, number, date, count, score, ranking, quote, prize, sponsor or claim about what happened. If the notes do not say who won, you do not write who won. If the notes do not give a number, you do not give one.

Rules
1. Keep EVERY fact in the notes: every name, number, date, place, result and role.
2. Add nothing. Descriptive and connective wording that carries no new fact is allowed; new information is not.
3. Keep the language(s) the notes are written in. Notes in Chinese stay in Chinese; notes in English stay in English; mixed notes keep both languages, with the Chinese rendered as proper Chinese and the English as proper English.
4. Stay close in length. Aim for 100-400 characters of Chinese or 80-250 words of English - enough to be useful, short enough that it is still a description and not an article.
5. The house terms are 哈工大（深圳）, HITSZ, HSIYC, 哈工大（深圳）国际青年俱乐部, HITSZ International Youth Club. Chinese uses full-width punctuation; English uses standard punctuation and no Chinese punctuation.
6. No headings, no bullet points, no markdown, no emoji, no first-person singular. Plain prose paragraphs.
7. Never invent a question's answer either: your questions ask the operator, they do not guess.
8. Keep names exactly as the operator wrote them. If a Chinese name is written in Latin letters ("ling yi laoshi"), leave it in Latin letters - guessing which characters it is spells a real person's name wrong, which is worse than leaving it romanised. Ask for the characters in "questions" instead. The same goes for an event name in only one language.
9. Keep the operator's own vocabulary for things you are unsure about ("five integrals" stays integrals; do not decide it means rounds). Ask in "questions" when the wording could mean two things.

Return ONE JSON object:
{"description": "<the improved description>",
 "questions": ["<up to 5 short questions about facts the notes leave out>"],
 "dropped": ["<any fact you could not keep, and why>"]}
"questions" asks about the things a reviewer will look for and the notes do not say - an exact count, the full name of a judge, the prize titles, who did what. Leave it [] when nothing important is missing. "dropped" is normally []."""


def build_description_developer_messages(text: str, doc_type: str = "") -> list[dict]:
    """The 'Develop this description' conversation: notes in, a better description out."""
    context = f"The article type is 「{doc_type}」.\n\n" if doc_type else ""
    return [
        {"role": "system", "content": DESCRIPTION_DEVELOPER_PROMPT},
        {"role": "user", "content": context + "NOTES FROM THE CLUB:\n" + text.strip()},
    ]


PHOTO_ANALYST_PROMPT = (
    "These are photos from one HSIYC (HITSZ International Youth Club) event. "
    "For EACH photo, report what is visible: setting/venue, stage or booth, how many people "
    "and what they are doing, any visible banners, signage, screens, logos or readable text, "
    "trophies/awards, and whether the shot works as a wide banner, a group shot or a detail shot. "
    "Never speculate about the identity of a person from their appearance. "
    "Return one JSON object with this shape: "
    '{"photos":[{"file":"<name>","scene":"...","people":"...","visible_text":["..."],'
    '"usable_as":"banner|group|detail","suggested_caption_en":"...","suggested_caption_cn":"..."}],'
    '"event_reconstruction":"two sentences on what this event appears to have been"}'
)


def build_photo_analyst_messages(photo_paths: Sequence[Path], photo_names: Sequence[str]) -> list[dict]:
    """Vision prompt: one labelled image part per photo, in the given order."""
    content: list[dict] = [{"type": "text", "text": PHOTO_ANALYST_PROMPT}]
    for path, name in zip(photo_paths, photo_names):
        content.append({"type": "text", "text": f"PHOTO FILE: {name}"})
        content.append(image_part(path))
    content.append(
        {"type": "text", "text": "Answer with the JSON object only, one entry per photo above."}
    )
    return [
        {
            "role": "system",
            "content": "You describe event photos for a club newsletter. You are precise, and you never guess identities.",
        },
        {"role": "user", "content": content},
    ]


def build_article_messages(
    brief: dict,
    brief_text: str,
    exemplars: Sequence[CorpusDoc],
    photo_report: dict | None = None,
    fix_instructions: Sequence[str] = (),
    doc_type: str = "",
) -> list[dict]:
    """Assemble the article-writing conversation."""
    user_parts: list[str] = []

    user_parts.append(
        "### TASK\n"
        f"Write the complete bilingual HSIYC article of type 「{doc_type or brief.get('doc_type') or '回顾'}」 "
        "for the event described below, matching the approved corpus exactly."
    )

    user_parts.append("### JSON CONTRACT (top-level keys must match)\n```json\n" + _compact_schema() + "\n```")

    user_parts.append("### HOUSE STYLE (distilled from the approved articles)\n" + _style_spec())

    checklist = _checklist()
    if checklist:
        user_parts.append("### WHY ARTICLES GET REJECTED - AVOID ALL OF THESE\n" + checklist)

    user_parts.append("### APPROVED ARTICLES TO IMITATE\n" + exemplar_block(exemplars))

    user_parts.append(
        "### STRUCTURED BRIEF (authoritative for facts)\n```json\n"
        + json.dumps(brief, ensure_ascii=False, indent=1)
        + "\n```"
    )

    description = str(brief.get("event_description") or "").strip()
    if description:
        user_parts.append(
            "### THE CLUB'S OWN DESCRIPTION OF THE EVENT (develop this - it is the spine)\n"
            + description
            + "\n\n"
            "This is the operator's own account, written in their own words and in whatever "
            "language they chose. Turn it into the article:\n"
            "* give it a shape - background, what actually happened, the moments that mattered, "
            "the result, what it means for the club;\n"
            "* rewrite note-form fragments as finished bilingual prose, and expand the passing "
            "details into proper sentences (who, where, how many, what was said);\n"
            "* keep every fact it states, including its numbers, names and dates;\n"
            "* do NOT reuse its wording verbatim, and do NOT add any fact, name, number, quote "
            "or sponsor it does not contain. If it is thin, write less - never invent filler."
        )

    if brief_text.strip():
        user_parts.append("### RAW NOTES FROM THE CLUB (also authoritative)\n" + brief_text.strip())

    if photo_report:
        user_parts.append(
            "### WHAT THE SUPPLIED PHOTOS ACTUALLY SHOW (use for photo_grid placement and captions; "
            "do not claim anything beyond this)\n```json\n"
            + json.dumps(photo_report, ensure_ascii=False, indent=1)
            + "\n```"
        )
        user_parts.append(
            "Place every uploaded photo exactly once across the article using kind=\"photo_grid\" blocks, "
            "distributing them where they fit the narrative (lead, mid-section, closing).\n"
            "IMPORTANT - photo layout: the approved corpus has NO multi-photo grid. Use ONE photo per "
            "photo_grid block (set layout to \"1x1\"). Only group photos into a block with layout "
            "\"carousel\" when they are genuinely the same moment under the club's carousel frame; never "
            "build a 2x2 or 3-up grid."
        )

    if fix_instructions:
        numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(fix_instructions, 1))
        user_parts.append(
            "### CORRECTIONS REQUIRED FROM THE PREVIOUS DRAFT\nThe previous draft failed review. "
            "Fix exactly these problems and change nothing else:\n" + numbered
        )

    user_parts.append(
        "### OUTPUT\nReturn ONE JSON object only - no prose, no markdown fence. "
        "Fill \"facts\" with every concrete fact and its source, and \"needs_editor\" with "
        "everything a human must confirm before submission."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]
