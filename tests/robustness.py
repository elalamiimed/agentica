"""Offline degradation tests: the agent must survive a broken vision call and bad input.

Real use is messier than the happy path - a photo the API rejects, a brief with nothing
usable in it, an article JSON that is not an article. None of those may crash the run or
silently produce a bundle with no article.

Uses monkeypatching, so it needs no API key and no network beyond what the agent itself
would do (the vision/API calls are stubbed out).

    <python> tests/robustness.py
"""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import pipeline, validate  # noqa: E402
from hsiyc_writer.config import Settings  # noqa: E402
from hsiyc_writer.deepseek import DeepSeekError  # noqa: E402
from hsiyc_writer.retrieval import Corpus  # noqa: E402

ARTICLE = {
    "meta": {"doc_type": "回顾", "slug": "robust"},
    "title": {"cn": "国际青年俱乐部 | 回顾：稳健性测试", "en": "Robustness Test"},
    "lead": {"cn": "这是一次稳健性测试，用来确认流程在异常输入下仍然能够完成。", "en": "This is a robustness test to confirm the pipeline still completes under bad input."},
    "sections": [
        {"number": "01", "heading_cn": "过程", "heading_en": "Process",
         "body": [{"kind": "bilingual", "cn": "流程在图片识别失败时应当继续写作，并把缺失的信息记录下来。",
                   "en": "The pipeline must keep writing when photo analysis fails and record what is missing."}]},
        {"number": "02", "heading_cn": "结果", "heading_en": "Result",
         "body": [{"kind": "bilingual", "cn": "文章依然可以生成，检查报告会提示照片未被使用。",
                   "en": "The article is still produced and the report flags the unused photos."}]},
        {"number": "03", "heading_cn": "结语", "heading_en": "Closing",
         "body": [{"kind": "bilingual", "cn": "感谢参与测试的每一位同学。", "en": "Thank you to every student who took part."}]},
    ],
    "closing": {"heading_cn": "结语", "heading_en": "Closing",
                "cn": "感谢参与测试的每一位同学。", "en": "Thank you to every student who took part."},
    "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
    "credits": {"文字": "A", "图片": "B", "排版": "C", "一审": "D", "二审": "E", "三审": "卢锦章"},
    "facts": [{"fact": "稳健性测试", "source": "brief"}],
    "needs_editor": ["照片识别失败，请人工补充图注"],
}


def main() -> int:
    failures: list[str] = []
    settings = Settings(api_key="stub-key-for-offline-test")
    corpus = Corpus.load()

    agent = pipeline.ArticleAgent(settings, corpus=corpus)

    # ---- 1. a broken vision call must not abort the run
    def exploding_vision(messages, **kwargs):
        raise DeepSeekError("simulated vision failure (HTTP 500)")

    real_photo = ROOT / "_work" / "webphotos"
    sample = sorted(real_photo.glob("*.png"))[:1]
    original_chat = agent.client.chat
    agent.client.chat = exploding_vision  # type: ignore[method-assign]
    try:
        report = agent.analyse_photos(sample) if sample else agent.analyse_photos([Path("x.png")])
    finally:
        agent.client.chat = original_chat  # type: ignore[method-assign]
    if report != {}:
        failures.append(f"vision failure should return {{}}, got {report!r}")
    if not any("photo analysis failed" in line for line in agent.log):
        failures.append("vision failure was not recorded in the run log")

    # ---- 2. no photos at all is a clean no-op
    if agent.analyse_photos([]) != {}:
        failures.append("analyse_photos([]) should return {}")

    # ---- 3. a missing photo file must not raise
    try:
        agent.analyse_photos([Path("definitely-not-here.png")])
    except Exception as exc:  # noqa: BLE001 - the point of the test
        failures.append(f"missing photo raised {type(exc).__name__}: {exc}")

    # ---- 4. the validator must never raise on malformed input
    bad_inputs = [
        {},
        {"sections": "not-a-list"},
        {"sections": [{"body": "not-a-list"}]},
        {"title": None, "lead": None, "sections": None, "closing": None,
         "signoff": None, "credits": None, "meta": None},
        {"sections": [{"body": [{"kind": "bilingual", "cn": 5, "en": None}]}]},
        {"facts": "not-a-list", "needs_editor": {"not": "a list"}},
    ]
    for i, payload in enumerate(bad_inputs, 1):
        try:
            report = validate.validate(copy.deepcopy(payload))
            if not isinstance(report.score, int):
                failures.append(f"malformed input {i}: score is not an int")
        except Exception as exc:  # noqa: BLE001 - the point of the test
            failures.append(f"malformed input {i} raised {type(exc).__name__}: {exc}")

    # ---- 5. rendering must not raise on an article with no photos and no toc
    try:
        from hsiyc_writer import pdfout, render

        minimal = copy.deepcopy(ARTICLE)
        minimal["sections"][0]["body"].append({"kind": "photo_grid", "photos": []})
        # Write under the workspace, not the system temp dir: the file sandbox may
        # deny the latter (and a real run would not use it either).
        scratch = ROOT / "_work" / "probe" / "robustness"
        scratch.mkdir(parents=True, exist_ok=True)
        html = render.to_html(minimal, None, {})
        if "国际青年俱乐部" not in html:
            failures.append("HTML render dropped the headline")
        render.to_markdown(minimal, None)
        pdf_path = scratch / "minimal.pdf"
        pdfout.write_article_pdf(minimal, pdf_path, {}, None, shrink=False)
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            failures.append("PDF was not written for the minimal article")
    except Exception as exc:  # noqa: BLE001 - the point of the test
        failures.append(f"rendering a minimal article raised {type(exc).__name__}: {exc}")

    # ---- 6. a corpus-similarity check with an empty corpus must not raise
    try:
        validate.validate(copy.deepcopy(ARTICLE), corpus_texts=[], corpus_labels=[])
    except Exception as exc:  # noqa: BLE001
        failures.append(f"empty corpus raised {type(exc).__name__}: {exc}")

    # ---- 7. missing API key must be reported, not crash at import
    try:
        Settings.load(require_key=True)
    except Exception as exc:  # noqa: BLE001
        from hsiyc_writer.config import ConfigError

        if not isinstance(exc, ConfigError):
            failures.append(f"missing key raised {type(exc).__name__} instead of ConfigError")

    if failures:
        print(f"robustness: {len(failures)} FAILURE(S)")
        for item in failures:
            print("  -", item)
        return 1
    print("robustness: OK - vision failure, malformed articles and empty inputs are all handled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
