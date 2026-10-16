"""The 'Develop this description' step: it must improve the notes without adding facts.

The box on the form takes rough notes, and one API call turns them into a description an
article can be written from. That is only safe if the rewrite is checked the same way the
article is: every figure and every Latin name in the result has to already exist in what
the operator typed. These cases prove the check catches an invented number and an invented
name, and - just as important - that it does not fire on a faithful rewrite.

No API key and no network: the client is faked.

    <python> tests/develop_cases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop, prompts  # noqa: E402

NOTES = (
    "The first round of the APEC Future Skills Challenge happened in A509 on 8 November. "
    "32 students from 7 countries signed up and we ran it as a 1v1 blitz: five integrals, "
    "90 seconds each. About 80 people stayed to the end. Tugsuu beat Brandon in the final. "
    "凌怡老师 judged and gave feedback afterwards."
)

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


class FakeReply:
    def __init__(self) -> None:
        self.text = "{}"

        class Usage:
            def as_dict(self) -> dict:
                return {"total_tokens": 42, "elapsed_s": 1.0, "model": "fake"}

        self.usage = Usage()


class FakeClient:
    """Returns whatever JSON the model 'wrote', and records the messages it was sent."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.messages: list[dict] = []
        self.calls = 0

    def json_chat(self, messages, **kwargs):
        self.calls += 1
        self.messages = messages
        return self.payload, FakeReply()


FAITHFUL = {
    "description": (
        "On 8 November the first round of the APEC Future Skills Challenge took place in A509. "
        "Thirty-two students from seven countries took part in a 1v1 blitz format in which each "
        "duel used five integrals and 90 seconds. About 80 people stayed until the end. Tugsuu "
        "beat Brandon in the final, and 凌怡老师 judged and gave feedback afterwards."
    ),
    "questions": ["How many students reached the final?", "What were the prize titles?"],
    "dropped": [],
}


def case_model_cannot_widen_the_whitelist() -> None:
    """On the free-form path the brief is model-authored, and it is authoritative material.

    `event_description` is handed to the writer as the spine of the article, so a
    normaliser that invented a fact there would also be whitelisting its own invention.
    The form path never calls the normaliser; this path must not trust the field either.
    """
    print("a model-authored brief cannot inject a description")
    from hsiyc_writer import pipeline
    agent = pipeline.ArticleAgent.__new__(pipeline.ArticleAgent)   # no corpus, no client
    agent.log = []
    agent.corpus = []
    agent.normalise_brief = lambda text, hint="": {
        "doc_type": "回顾",
        "event_description": "the club welcomed 999 guests",
        "highlights": [],
    }
    seen: dict = {}

    def fake_generate(brief, *args, **kwargs):
        seen["brief"] = brief
        return "generated"

    agent._generate = fake_generate
    result = agent.run("raw notes from the operator", write_outputs=False)
    check(result == "generated", "run() should return what _generate returned")
    check("event_description" not in seen["brief"],
          "a model-authored description must not reach the writer or the whitelist")
    check(seen["brief"].get("doc_type") == "回顾", "the rest of the brief must survive")


def case_guards() -> None:
    """Unusable input is refused before a token is spent."""
    print("guards")
    client = FakeClient(FAITHFUL)
    for text, label in (("", "empty notes"), ("   too short ", "notes under the minimum")):
        try:
            develop.develop_description(client, text)
            check(False, f"{label} should be refused")
        except develop.DescriptionError:
            pass
    check(client.calls == 0, "a refused input must not reach the API")

    try:
        develop.develop_description(client, "x" * (develop.MAX_CHARS + 1))
        check(False, "an over-long description should be refused")
    except develop.DescriptionError:
        pass
    check(client.calls == 0, "an over-long description must not reach the API")

    # A model that returns nothing usable is an error, not an empty box.
    try:
        develop.develop_description(FakeClient({"description": "   "}), NOTES)
        check(False, "an empty rewrite should be an error")
    except develop.DescriptionError:
        pass


def case_faithful() -> None:
    """A rewrite that keeps every fact passes, and its questions reach the operator."""
    print("a faithful rewrite")
    result = develop.develop_description(FakeClient(FAITHFUL), NOTES, doc_type="回顾")
    check(result["description"].startswith("On 8 November"), "the rewrite should be returned")
    check(result["original"] == NOTES.strip(), "the original notes should come back with it")
    check(result["questions"] == FAITHFUL["questions"], "the questions should be carried over")
    check(result["dropped"] == [], "nothing was dropped, so the list should be empty")
    check(result["unsourced"] == {"numbers": [], "dates": [], "names": []},
          f"a faithful rewrite must not be reported as unsourced, got {result['unsourced']}")
    check(result["usage"]["total_tokens"] == 42, "the token usage should be reported")


def case_representation_is_not_invention() -> None:
    """Writing a fact differently is not inventing it.

    Three shapes of the same false positive, all found in a live run:
      * `A509.` ends a sentence, so the room number must still be read as 509;
      * `8 november` and `11月8日` are the same day, so the 11 is not a new figure;
      * a title in front of a name is not part of the name.
    A checker that cries wolf here is worse than no checker, because the operator learns
    to click past it.
    """
    print("representation, not invention")
    notes = ("The first round happened on 8 november in A509. 32 students signed up, and we ran "
             "it as a 1v1 blitz: five integrals, 90 seconds each. About 80 people stayed. "
             "Tugsuu beat Brandon in the final. ling yi laoshi judged.")
    rewritten = ("11月8日，APEC 未来技能挑战赛首轮在 A509 举行。32 名学生报名参赛，赛制为 1v1 闪电战，"
                 "共 5 道积分题，每题 90 秒。约 80 人到场观赛。决赛中，Tugsuu 战胜 Brandon。"
                 "凌怡老师担任裁判。")
    clean = develop.unsourced(rewritten, notes)
    check(clean == {"numbers": [], "dates": [], "names": []},
          f"a faithful rewrite in the other language must be clean, got {clean}")

    # The full stop at the end of the note must not hide the number.
    check("509" in develop._figures(notes), "a number before a sentence-ending full stop must be read")
    check(develop._figures("in A509.") == develop._figures("在 A509 举行"),
          "the same room number written in two languages must compare equal")

    # A day written two ways is one day.
    check(develop._dates("8 november")[0] == develop._dates("11月8日")[0] == {"11-08"},
          "8 november and 11月8日 must normalise to the same date")
    check(develop._dates("Nov 8, 2026")[0] == {"2026-11-08"}, "an abbreviated month must parse")
    check(develop._dates("2026年11月8日")[0] == {"2026-11-08"}, "a full Chinese date must parse")
    check(develop._dates("2026-11-08")[0] == {"2026-11-08"}, "an ISO date must parse")
    check(develop._dates("no date here")[0] == set(), "text without a date must yield none")

    # A genuinely different day is still caught, even in the same month.
    moved = develop.unsourced("比赛于 11月9日 举行。", notes)
    check(moved["dates"] == ["11-09"], f"a moved date must be reported, got {moved}")
    # A date that appears nowhere in the notes at all.
    new_date = develop.unsourced("The finals were on 3 December.", notes)
    check(new_date["dates"] == ["12-03"], f"an added date must be reported, got {new_date}")

    # Two dates in one description, both rewritten in the other language.
    two_dates = develop.unsourced(
        "工作坊于 10月5日 和 10月12日 举行，每次 40 人。",
        "the workshop ran on 5 october and again on 12 october, 40 students each time",
    )
    check(two_dates == {"numbers": [], "dates": [], "names": []},
          f"two faithful dates must both be recognised, got {two_dates}")


def case_verifier_defects() -> None:
    """Every false positive the independent verifier found, pinned as a test.

    Each of these was observed on the real code, not imagined: they are the reason the
    check can be trusted at all - a checker that accuses good copy teaches the operator to
    ignore it.
    """
    print("the verifier's false positives")
    from hsiyc_writer.validate import canonical_dates

    # 1. A date range is two dates. Reading only the first left the other day looking
    #    invented, and accused a faithful CN -> EN rewrite of inventing both a number and a day.
    check(develop.unsourced("The event was held from 8 to 9 November.", "活动于11月8日至9日举行。")
          == {"numbers": [], "dates": [], "names": []},
          "a date range written in the other language must be clean")
    check(canonical_dates("11月8日至9日")[0] == {"11-08", "11-09"}, "11月8日至9日 is two dates")
    check(canonical_dates("11月8日、9日")[0] == {"11-08", "11-09"}, "11月8日、9日 is two dates")
    check(canonical_dates("11月8-9日")[0] == {"11-08", "11-09"}, "11月8-9日 is two dates")
    check(canonical_dates("8-9 November")[0] == {"11-08", "11-09"}, "8-9 November is two dates")
    check(canonical_dates("November 8-9")[0] == {"11-08", "11-09"}, "November 8-9 is two dates")
    check(canonical_dates("8 to 9 November")[0] == {"11-08", "11-09"}, "8 to 9 November is two dates")
    # ... but two separate dates either side of a comma are not a range.
    check(canonical_dates("11月8日、12月9日")[0] == {"11-08", "12-09"},
          "a comma-separated second date must not be swallowed as a range end")
    # A range whose end day really moved is still caught.
    moved_range = develop.unsourced("活动于11月8日至10日举行。", "活动于11月8日至9日举行。")
    check(moved_range["dates"] == ["11-10"], f"a moved range end must be reported, got {moved_range}")

    # 2. `8th of November 2026` read as 2026-11-20: the day pattern ate the year's first two
    #    digits. The bogus day reached the operator-facing warning.
    check(canonical_dates("8th of November 2026")[0] == {"2026-11-08"},
          f"8th of November 2026 must be one date, got {canonical_dates('8th of November 2026')[0]}")
    check(canonical_dates("the 8th of November")[0] == {"11-08"}, "a year-less ordinal date must parse")
    check(canonical_dates("November 2026")[0] == set(),
          f"a month and a year is not a day, got {canonical_dates('November 2026')[0]}")

    # 3. Full-width digits are what a Chinese IME produces.
    check(develop.unsourced("共有32名学生报名。", "共有３２名学生报名。")
          == {"numbers": [], "dates": [], "names": []},
          "a full-width count must equal its ASCII form")
    check(develop.unsourced("The event was held in Ａ５０９.", "The event was held in A509.")
          == {"numbers": [], "dates": [], "names": []},
          "a full-width room number must equal its ASCII form")
    check(canonical_dates("２０２６年１１月８日")[0] == {"2026-11-08"}, "full-width dates must parse")

    # 4. "march" is a verb before it is a month when it is lowercase and alone.
    check(develop.unsourced("We march 5 kilometres", "We march five kilometres")
          == {"numbers": [], "dates": [], "names": []},
          "'we march 5 kilometres' must not hide the 5 behind a fabricated 5 March")
    check(canonical_dates("We march 5 kilometres")[0] == set(), "a lowercase 'march' is not a month")
    check(canonical_dates("March 5")[0] == {"03-05"}, "a capitalised month still parses")
    check(canonical_dates("november 8, 2026")[0] == {"2026-11-08"},
          "a lowercase month with a year still parses")

    # 5. Impossible days are not dates.
    check(canonical_dates("2026-02-30")[0] == set(), "30 February is not a date")
    check(canonical_dates("31 February")[0] == set(), "31 February is not a date")
    check(canonical_dates("2026-02-28")[0] == {"2026-02-28"}, "28 February is a date")
    check(canonical_dates("2024-02-29")[0] == {"2024-02-29"}, "29 February 2024 is a leap day")

    # The shapes the verifier proved clean must stay clean.
    for text in ("A509", "Room 3", "3号场", "1v1", "90 seconds", "15:00-18:00", "双打12对",
                 "5.5", "", None):
        check(canonical_dates(text)[0] == set(), f"{text!r} must not be read as a date")
    check(canonical_dates("HS-2026-11-08")[0] == {"2026-11-08"},
          "a prefixed ISO date is still a date")
    check(canonical_dates("May I say 8 students came?")[0] == set(),
          "'May' as a verb must not fabricate a date")


def case_untouched_facts_stay_allowed() -> None:
    """The strictness must not become a wall: legitimate rewrite moves are accepted."""
    print("legitimate rewrites")
    notes = ("the workshop ran 2026-11-08 in A509. 48 students came. two tutors, Zhang laoshi "
             "and Wang laoshi, ran the session.")
    ok = ("2026年11月8日，工作坊在 A509 举行，48 名学生参加，由 Zhang laoshi 与 Wang laoshi 两位"
          "辅导老师主讲。")
    check(develop.unsourced(ok, notes) == {"numbers": [], "dates": [], "names": []},
          f"a faithful Chinese rendering must be clean, got {develop.unsourced(ok, notes)}")
    # The year is a real addition and is reported as one.
    year_added = develop.unsourced("工作坊于 2026年11月8日 举行。", "the workshop ran on 8 november in A509")
    check(year_added["numbers"] == ["2026"],
          f"a year the operator never wrote should be reported, got {year_added}")


def case_spelling_equivalence() -> None:
    """`five integrals` -> `5 integrals` is not an invented fact.

    This is the same trap the article check fell into: a number the operator spelt out in
    words is the number, and a rewrite that writes it in digits must not be accused of
    inventing it.
    """
    print("spelt-out numbers")
    result = develop.develop_description(FakeClient(FAITHFUL), NOTES)
    check("5" not in result["unsourced"]["numbers"],
          f"a number written in words must be recognised in digits, got {result['unsourced']}")
    check("7" not in result["unsourced"]["numbers"],
          f"'seven countries' must be recognised, got {result['unsourced']}")
    check("32" not in result["unsourced"]["numbers"],
          f"'Thirty-two' must be recognised, got {result['unsourced']}")


def case_invented_number() -> None:
    """An invented figure is caught, exactly as the article check would catch it."""
    print("an invented figure")
    bad = dict(FAITHFUL, description=FAITHFUL["description"] + " In total 512 students attended.")
    result = develop.develop_description(FakeClient(bad), NOTES)
    check(result["unsourced"]["numbers"] == ["512"],
          f"the invented figure should be reported, got {result['unsourced']}")
    # The useful numbers are untouched.
    for known in ("32", "90", "80"):
        check(known not in result["unsourced"]["numbers"],
              f"{known} is in the notes and must not be reported")

    # Figures are compared against the notes, not against the article brief.
    no_numbers = develop.develop_description(
        FakeClient(dict(FAITHFUL, description="The event happened and everyone enjoyed it.")), NOTES
    )
    check(no_numbers["unsourced"]["numbers"] == [], "a rewrite with no figures has nothing to report")


def case_invented_name() -> None:
    """A name the operator never wrote is caught; the ones they did write are not."""
    print("an invented name")
    bad = dict(FAITHFUL, description=FAITHFUL["description"] + " Judge Alan Turing praised the format.")
    result = develop.develop_description(FakeClient(bad), NOTES)
    check(result["unsourced"]["names"] == ["Alan Turing"],
          f"the invented name should be reported, got {result['unsourced']}")

    fine = dict(FAITHFUL, description=FAITHFUL["description"] + " Tugsuu and Brandon both spoke.")
    check(develop.develop_description(FakeClient(fine), NOTES)["unsourced"]["names"] == [],
          "names copied from the notes must not be reported")

    # A title in front of a name is not part of the name, and a name that is already in
    # the notes stays allowed however it is written.
    titled = dict(FAITHFUL, description=FAITHFUL["description"] + " Professor Alan Turing spoke.")
    check(develop.develop_description(FakeClient(titled), NOTES)["unsourced"]["names"] == ["Alan Turing"],
          "a title should be trimmed off the reported name")
    known = dict(FAITHFUL, description="Professor Ling Yi judged the finals.")
    check(develop.develop_description(FakeClient(known), NOTES)["unsourced"]["names"] == [],
          "a name the operator supplied must not be reported")


def case_questions_capped() -> None:
    """The operator gets a short list of questions, never a wall of them."""
    print("questions")
    many = dict(FAITHFUL, questions=[f"Question {i}?" for i in range(12)])
    result = develop.develop_description(FakeClient(many), NOTES)
    check(len(result["questions"]) == develop.MAX_QUESTIONS,
          f"at most {develop.MAX_QUESTIONS} questions, got {len(result['questions'])}")
    check(develop.develop_description(FakeClient(dict(FAITHFUL, questions=[])), NOTES)["questions"] == [],
          "no questions is a normal answer")
    check(develop.develop_description(
        FakeClient(dict(FAITHFUL, questions="Who judged?")), NOTES)["questions"] == ["Who judged?"],
        "a single question returned as a string should still be usable")


def case_prompt() -> None:
    """The prompt carries the notes, the article type, and the no-invention rules."""
    print("the prompt")
    messages = prompts.build_description_developer_messages(NOTES, "回顾")
    check(len(messages) == 2 and messages[0]["role"] == "system", "the prompt needs a system message")
    system = messages[0]["content"]
    check("may NOT introduce a single fact" in system,
          "the system prompt must forbid invented facts")
    check("Keep EVERY fact in the notes" in system, "the system prompt must require keeping the facts")
    user = messages[1]["content"]
    check(NOTES in user, "the notes must reach the model")
    check("回顾" in user, "the article type should be passed as context")
    check(NOTES in prompts.build_description_developer_messages(NOTES)[1]["content"],
          "the prompt must work without an article type")

    # The article prompt develops the same text, and tells the model not to paste it.
    article_messages = prompts.build_article_messages(
        {"doc_type": "回顾", "event_description": NOTES}, "raw notes", []
    )
    blob = article_messages[1]["content"]
    check("THE CLUB'S OWN DESCRIPTION OF THE EVENT" in blob,
          "the article prompt should give the description its own block")
    check(NOTES in blob, "the description must reach the article writer")
    check("do NOT reuse its wording verbatim" in blob,
          "the article prompt must forbid pasting the description")
    check("EVENT DESCRIPTION" not in prompts.build_article_messages({"doc_type": "回顾"}, "", [])[1]["content"],
          "an empty description should add no block at all")


def case_web_endpoint() -> None:
    """The endpoint refuses bad input without a key and without a network call."""
    print("the /api/develop endpoint")
    from hsiyc_writer import web

    class Stub:
        api_key = ""

    class Capture(web.Handler):
        def __init__(self, body: bytes) -> None:
            self.code = None
            self.payload = None
            self._body = body
            self.settings = Stub()

        def _read_body(self):
            return self._body

        def _json(self, code, payload):
            self.code, self.payload = code, payload

    handler = Capture(b"not json at all")
    handler._develop_description()
    check(handler.code == 400 and "invalid JSON" in handler.payload.get("error", ""),
          f"malformed JSON should be a 400, got {handler.code} {handler.payload}")

    handler = Capture(json.dumps({"text": NOTES}).encode("utf-8"))
    handler._develop_description()
    check(handler.code == 400 and "API key" in handler.payload.get("error", ""),
          f"no key should be a clear 400, got {handler.code} {handler.payload}")

    # An empty box must be refused before the key is even considered.
    class Keyed(Stub):
        api_key = "sk-not-a-real-key"

    handler = Capture(json.dumps({"text": "hi"}).encode("utf-8"))
    handler.settings = Keyed()
    handler._develop_description()
    check(handler.code == 400 and "at least" in handler.payload.get("error", ""),
          f"a stub of a description should be a 400, got {handler.code} {handler.payload}")


def main() -> int:
    case_guards()
    case_faithful()
    case_representation_is_not_invention()
    case_verifier_defects()
    case_untouched_facts_stay_allowed()
    case_model_cannot_widen_the_whitelist()
    case_spelling_equivalence()
    case_invented_number()
    case_invented_name()
    case_questions_capped()
    case_prompt()
    case_web_endpoint()

    if failures:
        print(f"\ndevelop_cases: {len(failures)} FAILURE(S)")
        for item in failures:
            print("  -", item)
        return 1
    print("\ndevelop_cases: OK - the rewrite keeps every fact the operator wrote, and is caught "
          "the moment it invents one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
