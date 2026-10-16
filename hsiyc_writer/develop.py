"""Develop the operator's rough event description into something worth building on.

The intake form asks one open question - "describe the event in your own words" - and
people answer it the way they would text a colleague: fragments, half a sentence, the
result but not the count, Chinese in one clause and English in the next. That is the right
answer to give; it is not yet a description an article can be written from.

This module is the single API call behind the "Develop this description" button. It hands
the notes to the model as an *editor*, not a reporter, and then - crucially - checks the
result the same way the article check works: every figure, date and Latin name in the
improved text must already exist in what the operator typed. Writing a fact differently is
not inventing it, so representations are normalised before comparing. The model is asked
not to invent; this makes the promise testable, and the page shows anything that slipped
through.

The operator keeps the last word: the improved text lands back in the box, editable, with
the original one click away.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from .deepseek import DeepSeekClient
from .prompts import build_description_developer_messages
from .validate import LATIN_NAME_RE, canonical_dates, normalise_digits, number_words

# Below this there is nothing to develop; above it the operator has pasted an article.
MIN_CHARS = 12
MAX_CHARS = 8000

MAX_QUESTIONS = 5

# The same numbers the article check treats as structural noise rather than facts.
_NOISE = {"1", "2", "3", "01", "02", "03"}

# Deliberately looser than the article check's STANDALONE_NUMBER_RE, which excludes a
# number followed by "." so that "1.5" stays one number. Here the notes are prose: "in
# A509." ends a sentence, and reading that as "no 509 at all" made the check accuse a
# faithful rewrite of inventing the room number the operator had just written.
_FIGURE_RE = re.compile(r"(?<![\d.])\d+(?:[.,]\d+)?(?!\d)")

# The project's single date model lives in validate.py, because the intake form needs it
# too: it warns when the description mentions a day that is not the event date. Kept under
# this name because it is how the rest of this module reads.
_dates = canonical_dates


class DescriptionError(ValueError):
    """The notes cannot be developed (empty, too short, or too long)."""


def _blank(text: str, spans: Sequence[tuple[int, int]]) -> str:
    chars = list(text or "")
    for start, end in spans:
        for index in range(max(0, start), min(len(chars), end)):
            chars[index] = " "
    return "".join(chars)


def _figures(text: str) -> set[str]:
    """Every number in ``text``, digits and spelt-out forms alike, with dates left out."""
    _, blanks = _dates(text)
    stripped = _blank(normalise_digits(text), blanks)
    figures = set(_FIGURE_RE.findall(stripped))
    figures |= number_words(stripped)
    return figures - _NOISE


def _latin_names(text: str) -> set[str]:
    return {_trim_title(name) for name in LATIN_NAME_RE.findall(text or "")}


# "Judge Alan Turing" is one name-shaped match, but the title is not part of the name. The
# operator seeing "Judge Alan Turing is not in your notes" would have to work out which part
# is the problem, so report the person.
_TITLES = frozenset({
    "Dr", "Prof", "Professor", "Judge", "Mr", "Mrs", "Ms", "Miss", "Coach", "Captain",
    "Chair", "Dean", "Director", "President", "Teacher", "Sir",
})


def _trim_title(name: str) -> str:
    parts = name.split()
    while len(parts) > 1 and parts[0] in _TITLES:
        parts = parts[1:]
    return " ".join(parts)


def unsourced(improved: str, source: str) -> dict[str, list[str]]:
    """Facts in ``improved`` that the operator never wrote.

    Only what can be checked mechanically is reported: figures (digits or spelt out),
    dates, and Latin personal names. A rephrased sentence cannot be verified here - and
    neither can a romanised Chinese name turned into characters - which is exactly why the
    operator still reads the result before generating.
    """
    source_lower = (source or "").lower()
    stray_figures = sorted(_figures(improved) - _figures(source))

    source_dates, _ = _dates(source)
    source_days = {date[-5:] for date in source_dates}
    stray_dates = sorted(
        date for date in _dates(improved)[0]
        if date not in source_dates and date[-5:] not in source_days
    )

    stray_names = sorted(
        name for name in _latin_names(improved)
        if len(name.split()) >= 2 and name.lower() not in source_lower
    )
    return {"numbers": stray_figures, "dates": stray_dates, "names": stray_names}


def develop_description(
    client: DeepSeekClient,
    text: str,
    doc_type: str = "",
) -> dict[str, Any]:
    """Return an improved description, the questions it raises, and anything unsourced.

    Raises :class:`DescriptionError` when the notes themselves are unusable, and lets
    ``DeepSeekError`` propagate when the API fails - the caller decides how to report it.
    """
    notes = (text or "").strip()
    if len(notes) < MIN_CHARS:
        raise DescriptionError(
            f"Write at least {MIN_CHARS} characters before asking for a rewrite - "
            "there is nothing to develop yet."
        )
    if len(notes) > MAX_CHARS:
        raise DescriptionError(
            f"These notes are {len(notes)} characters; the limit is {MAX_CHARS}. "
            "Trim them to a description rather than a draft article."
        )

    brief, reply = client.json_chat(
        build_description_developer_messages(notes, doc_type),
        temperature=0.3,
        max_tokens=1600,
    )

    description = str(brief.get("description") or "").strip()
    if not description:
        raise DescriptionError(
            "The model returned no description. Nothing was changed - press the button again."
        )

    questions = [
        str(q).strip()
        for q in _as_list(brief.get("questions"))
        if str(q).strip()
    ][:MAX_QUESTIONS]
    dropped = [str(d).strip() for d in _as_list(brief.get("dropped")) if str(d).strip()]

    return {
        "description": description,
        "questions": questions,
        "dropped": dropped,
        "unsourced": unsourced(description, notes),
        "original": notes,
        "usage": reply.usage.as_dict(),
    }


def _as_list(value: Any) -> Sequence[Any]:
    if isinstance(value, (list, tuple)):
        return value
    if isinstance(value, str) and value.strip():
        return [value]
    return ()
