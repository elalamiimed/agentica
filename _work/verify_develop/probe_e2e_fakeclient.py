"""End-to-end through develop_description with a fake client (no API spend)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop, prompts  # noqa: E402


class FakeReply:
    text = "{}"

    class Usage:
        @staticmethod
        def as_dict() -> dict:
            return {"total_tokens": 42, "elapsed_s": 1.0, "model": "fake"}

    usage = Usage()


class FakeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.messages: list[dict] = []
        self.calls = 0

    def json_chat(self, messages, **kwargs):
        self.calls += 1
        self.messages = messages
        return self.payload, FakeReply()


NOTES = "活动于11月8日至9日在 A509 举行，共有32名同学报名，ling yi laoshi 担任评委。"
FAITHFUL = ("The event ran from 8 to 9 November in A509. Thirty-two students signed up, and "
            "ling yi laoshi served as a judge.")

print("### develop_description with a faithful rewrite")
result = develop.develop_description(
    FakeClient({"description": FAITHFUL, "questions": ["How many reached the final?"], "dropped": []}),
    NOTES, doc_type="回顾")
print(f"  unsourced   : {result['unsourced']}")
print(f"  questions   : {result['questions']}")
print(f"  original    : {result['original'] == NOTES.strip()}")
print(f"  usage       : {result['usage']}")

print("\n### the developer prompt actually carries the notes and the doc type")
client = FakeClient({"description": FAITHFUL})
develop.develop_description(client, NOTES, doc_type="回顾")
system = client.messages[0]["content"]
user = client.messages[1]["content"]
print(f"  system == DESCRIPTION_DEVELOPER_PROMPT : {system == prompts.DESCRIPTION_DEVELOPER_PROMPT}")
print(f"  user carries the notes                : {NOTES.strip() in user}")
print(f"  user carries the doc type             : {'回顾' in user}")
print(f"  rule 8 (keep romanised names) present : {'leave it in Latin letters' in system}")
print(f"  rule 9 (keep operator vocabulary)     : {'five integrals' in system}")

print("\n### guards")
for text, label in (("", "empty"), ("  short ", "under MIN_CHARS"), ("x" * (develop.MAX_CHARS + 1), "over MAX_CHARS")):
    try:
        develop.develop_description(FakeClient({"description": "x"}), text)
        print(f"  {label:16} -> NOT refused (defect)")
    except develop.DescriptionError as exc:
        print(f"  {label:16} -> refused: {str(exc)[:60]}")
try:
    develop.develop_description(FakeClient({"description": "   "}), NOTES)
    print("  empty rewrite    -> NOT refused (defect)")
except develop.DescriptionError as exc:
    print(f"  empty rewrite    -> refused: {str(exc)[:60]}")
