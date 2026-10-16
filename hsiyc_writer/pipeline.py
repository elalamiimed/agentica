"""The generation pipeline.

    brief (messy notes)  ->  structured brief      (LLM, JSON mode)
    event photos         ->  what the photos show  (LLM, vision - optional)
    corpus               ->  nearest approved article(s) as exemplars (local)
    all of the above     ->  bilingual article JSON (LLM, JSON mode)
                         ->  deterministic validation
                         ->  targeted repair pass (bounded, only if it failed)
                         ->  renderers (.html / .docx / .pdf) + check report
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence

from . import prompts, validate
from .config import OUTPUT_DIR, Settings
from .deepseek import DeepSeekClient, DeepSeekError, Usage
from .retrieval import Corpus, CorpusDoc

SUPPORTED_PHOTOS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")

TITLE_PREFIX = "国际青年俱乐部"


@dataclass
class GenerationResult:
    article: dict
    report: validate.Report
    brief: dict = field(default_factory=dict)
    brief_text: str = ""
    photo_report: dict = field(default_factory=dict)
    exemplars: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    attempts: int = 0
    log: list[str] = field(default_factory=list)
    output_dir: Path | None = None

    def as_dict(self) -> dict:
        return {
            "article": self.article,
            "check": self.report.as_dict(),
            "brief": self.brief,
            "brief_text": self.brief_text,
            "photo_report": self.photo_report,
            "exemplars": self.exemplars,
            "usage": self.usage,
            "attempts": self.attempts,
            "log": self.log,
            "output_dir": str(self.output_dir) if self.output_dir else "",
        }


class ArticleAgent:
    """One instance per run; holds the corpus and the API client."""

    def __init__(self, settings: Settings, corpus: Corpus | None = None):
        self.s = settings
        self.client = DeepSeekClient(settings)
        self.corpus = corpus if corpus is not None else Corpus.load()
        self.log: list[str] = []

    # ------------------------------------------------------------------ helpers
    def _note(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"{stamp}  {message}")

    # ------------------------------------------------------------------- stages
    def normalise_brief(self, brief_text: str, doc_type_hint: str = "") -> dict:
        messages = prompts.build_brief_normaliser_messages(brief_text, doc_type_hint)
        try:
            brief, _ = self.client.json_chat(messages, temperature=0.1, max_tokens=2500)
            self._note("brief normalised")
            return brief
        except DeepSeekError as exc:
            self._note(f"brief normalisation failed ({exc}); continuing with raw notes only")
            return {"raw_notes": brief_text, "doc_type": doc_type_hint or "", "missing": ["structured brief unavailable"]}

    def analyse_photos(self, photo_paths: Sequence[Path]) -> dict:
        candidates = [p for p in photo_paths if p.suffix.lower() in SUPPORTED_PHOTOS]
        if not candidates or not self.s.vision_enabled:
            return {}
        # A path can look like a photo and still not exist (a renamed directory, a
        # deleted upload). Skipping it keeps the run alive; image_part would raise.
        photos: list[Path] = []
        for path in candidates:
            if path.is_file():
                photos.append(path)
            else:
                self._note(f"skipping missing photo: {path.name}")
        if not photos:
            self._note("no readable photos to analyse")
            return {}
        photos = photos[: self.s.max_photos]
        messages = prompts.build_photo_analyst_messages(photos, [p.name for p in photos])
        try:
            report, _ = self.client.json_chat(
                messages, model=self.s.vision_model, temperature=0.2, max_tokens=4000
            )
            report.setdefault("photos", [])
            self._note(f"vision read {len(photos)} photo(s)")
            return report
        except DeepSeekError as exc:
            self._note(f"photo analysis failed ({exc}); continuing without photo descriptions")
            return {}

    def pick_exemplars(self, query: str, k: int = 2, doc_type: str = "") -> list[CorpusDoc]:
        hits = self.corpus.search(query, k=k, kind=doc_type or None)
        docs = [doc for doc, score in hits if score > 0.02] or [doc for doc, _ in hits]
        self._note("exemplars: " + ", ".join(f"{d.slug}" for d in docs) if docs else "no exemplars found")
        return docs

    def write_article(
        self,
        brief: dict,
        brief_text: str,
        exemplars: Sequence[CorpusDoc],
        photo_report: dict | None = None,
        doc_type: str = "",
    ) -> dict:
        messages = prompts.build_article_messages(
            brief, brief_text, exemplars, photo_report=photo_report, doc_type=doc_type
        )
        article, reply = self.client.json_chat(messages, temperature=self.s.temperature, max_tokens=self.s.max_tokens)
        self._note(
            f"draft written ({reply.model}, {reply.elapsed_s:.1f}s, "
            f"{reply.usage.completion_tokens if reply.usage else 0} completion tokens)"
        )
        return article

    def repair(
        self,
        article: dict,
        report: validate.Report,
        brief: dict,
        brief_text: str,
        exemplars: Sequence[CorpusDoc],
        photo_report: dict | None = None,
        doc_type: str = "",
    ) -> dict:
        """One targeted repair pass driven by the validator's error list."""
        problems = [f"{f.code} @ {f.location or 'article'}: {f.message}" for f in report.errors]
        if not problems:
            problems = [f"{f.code} @ {f.location or 'article'}: {f.message}" for f in report.warnings]
        if not problems:
            return article
        base = prompts.build_article_messages(
            brief, brief_text, exemplars, photo_report=photo_report, doc_type=doc_type,
            fix_instructions=problems,
        )
        # Give the model its own previous draft so the repair is an edit, not a rewrite.
        base.append(
            {
                "role": "assistant",
                "content": json.dumps(article, ensure_ascii=False),
            }
        )
        base.append(
            {
                "role": "user",
                "content": "Here is the draft again with the fixes applied. Return the complete corrected JSON object only.",
            }
        )
        try:
            repaired, reply = self.client.json_chat(base, temperature=0.3, max_tokens=self.s.max_tokens)
            self._note(f"repair pass applied ({len(problems)} issue(s), {reply.elapsed_s:.1f}s)")
            return repaired
        except DeepSeekError as exc:
            self._note(f"repair pass failed ({exc}); keeping the first draft")
            return article

    # --------------------------------------------------------------- top level
    def run(
        self,
        brief_text: str,
        photos: Sequence[Path] = (),
        doc_type: str = "",
        repair_rounds: int = 1,
        require_toc: bool = False,
        write_outputs: bool = True,
        output_root: Path | None = None,
        progress=None,
        art_backend: str = "auto",
        deck: bool = True,
    ) -> GenerationResult:
        """Generate from free-form notes (the brief is normalised by the model first)."""
        step = self._stepper(progress)
        started = time.time()
        step(f"corpus loaded: {len(self.corpus)} approved article(s)")
        brief = self.normalise_brief(brief_text, doc_type)
        # On this path the structured brief is written by the model, and every string in it
        # is authoritative material the check traces facts back to. `event_description` gets
        # special treatment: it is handed to the writer as "the spine of the article", so a
        # normaliser could both invent a fact and whitelist its own invention in one move.
        # The operator's own words are already here as the raw notes, so drop the field and
        # let the notes speak. (The form path never calls the normaliser at all.)
        brief.pop("event_description", None)
        return self._generate(
            brief, brief_text, doc_type, photos, repair_rounds,
            require_toc, write_outputs, output_root, started, step,
            art_backend=art_backend, deck=deck,
        )

    def run_from_answers(
        self,
        answers: dict,
        photos: Sequence[Path] = (),
        repair_rounds: int = 1,
        require_toc: bool = False,
        write_outputs: bool = True,
        output_root: Path | None = None,
        progress=None,
        art_backend: str = "auto",
        deck: bool = True,
    ) -> GenerationResult:
        """Generate from the intake form.

        The operator has already supplied every fact as a labelled field, so there is
        nothing to normalise: the structured brief is built directly. That removes one
        API call and, more importantly, removes any chance of the model reinterpreting
        a date, a name or a count on the way in.
        """
        from .form import answers_to_brief, answers_to_structured_brief

        step = self._stepper(progress)
        started = time.time()
        step(f"corpus loaded: {len(self.corpus)} approved article(s)")
        brief = answers_to_structured_brief(answers)
        brief_text = answers_to_brief(answers)
        step("intake form accepted; using the answers as the source of truth")
        if brief.get("toc", {}).get("previous") or brief.get("toc", {}).get("next"):
            require_toc = True
        return self._generate(
            brief, brief_text, str(brief.get("doc_type") or ""), photos, repair_rounds,
            require_toc, write_outputs, output_root, started, step,
            art_backend=art_backend, deck=deck,
        )

    def _stepper(self, progress):
        def step(message: str) -> None:
            self._note(message)
            if progress:
                progress(message)

        return step

    def _generate(
        self,
        brief: dict,
        brief_text: str,
        doc_type: str,
        photos: Sequence[Path],
        repair_rounds: int,
        require_toc: bool,
        write_outputs: bool,
        output_root: Path | None,
        started: float,
        step,
        art_backend: str = "auto",
        deck: bool = True,
    ) -> "GenerationResult":
        effective_type = doc_type or str(brief.get("doc_type") or "")

        photo_report = self.analyse_photos(photos)
        query = " ".join(
            str(x) for x in (
                brief_text,
                brief.get("title_cn", ""), brief.get("title_en", ""),
                effective_type, brief.get("programme", ""),
                " ".join(map(str, brief.get("highlights", []) or [])),
                " ".join(map(str, brief.get("winners", []) or [])),
            )
        )
        exemplars = self.pick_exemplars(query, k=2, doc_type=effective_type)

        article = self.write_article(brief, brief_text, exemplars, photo_report, effective_type)
        article = self._postprocess(article, brief, effective_type)

        expected_photos = [p.name for p in photos if p.suffix.lower() in SUPPORTED_PHOTOS]
        report = self._check(article, brief, expected_photos, require_toc, brief_text)
        step(f"validation: score {report.score}/100, {len(report.errors)} error(s), {len(report.warnings)} warning(s)")

        attempts = 1
        rounds = 0
        while not report.ok and rounds < max(0, repair_rounds):
            rounds += 1
            step(f"repair round {rounds} for {len(report.errors)} error(s)")
            article = self.repair(article, report, brief, brief_text, exemplars, photo_report, effective_type)
            article = self._postprocess(article, brief, effective_type)
            report = self._check(article, brief, expected_photos, require_toc, brief_text)
            attempts += 1
            step(f"validation after repair {rounds}: score {report.score}/100, {len(report.errors)} error(s)")

        result = GenerationResult(
            article=article,
            report=report,
            brief=brief,
            brief_text=brief_text,
            photo_report=photo_report,
            exemplars=[d.slug for d in exemplars],
            usage=self.client.usage.as_dict(),
            attempts=attempts,
            log=list(self.log),
        )
        result.usage["elapsed_s"] = round(time.time() - started, 1)

        if write_outputs:
            from .render import write_all

            root = output_root or OUTPUT_DIR
            result.output_dir = write_all(result, root, art_backend=art_backend,
                                          art=art_backend != "none", deck=deck)
            step(f"outputs written to {result.output_dir}")

        step("done")
        return result

    # ---------------------------------------------------------------- internals
    def _check(
        self,
        article: dict,
        brief: dict,
        expected_photos: Sequence[str],
        require_toc: bool,
        brief_text: str = "",
    ) -> validate.Report:
        # The raw notes are authoritative material too, so include them when tracing
        # numbers and names back to what the operator actually supplied.
        brief_for_check = dict(brief or {})
        if brief_text:
            brief_for_check.setdefault("raw_notes", brief_text)
        return validate.validate(
            article,
            brief=brief_for_check,
            expected_photos=expected_photos,
            corpus_texts=[doc.text for doc in self.corpus.docs],
            corpus_labels=[doc.slug for doc in self.corpus.docs],
            require_toc=require_toc,
            require_photos=bool(expected_photos),
        )

    def _postprocess(self, article: dict, brief: dict, doc_type: str) -> dict:
        """Deterministic clean-up so the model does not have to be perfect."""
        if not isinstance(article, dict):
            raise DeepSeekError("The model did not return an article object.")

        article.setdefault("meta", {})
        meta = article["meta"]
        meta.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))
        meta.setdefault("model", self.s.text_model)
        if doc_type:
            meta["doc_type"] = doc_type
        if self.client.usage.model:
            meta["model"] = self.client.usage.model

        title = article.setdefault("title", {})
        cn = str(title.get("cn", "")).strip()
        # The corpus uses the ASCII "|" in the headline formula (full-width ｜ appears in a
        # couple of articles, but ASCII is the common form), so normalise it and keep one
        # space on each side.
        if cn:
            cn = re.sub(r"\s*[|｜]\s*", " | ", cn.replace("｜", "|")).strip()
        if cn and "国际青年俱乐部" not in cn and "HSIYC" not in cn:
            # Apply the house headline formula without disturbing the model's wording.
            cn = f"{TITLE_PREFIX} | {cn}"
        title["cn"] = cn

        article.setdefault("signoff", {})
        article["signoff"].setdefault("cn", validate.OFFICIAL_SIGNOFF_CN)
        article["signoff"].setdefault("en", validate.OFFICIAL_SIGNOFF_EN)

        article.setdefault("closing", {})
        article["closing"].setdefault("heading_cn", "结语")
        article["closing"].setdefault("heading_en", "Closing")

        credits = article.setdefault("credits", {})
        brief_credits = (brief or {}).get("credits") or {}
        if isinstance(brief_credits, dict):
            for role in validate.CREDIT_ROLES:
                value = brief_credits.get(role)
                if value and (not credits.get(role) or validate.is_placeholder(str(credits.get(role, "")))):
                    credits[role] = value

        slug = str(meta.get("slug", "")).strip()
        if not slug:
            slug = _slugify(cn or str(title.get("en", "")) or "hsiyc-article")
        meta["slug"] = slug

        article.setdefault("needs_editor", [])
        if not isinstance(article["needs_editor"], list):
            article["needs_editor"] = [str(article["needs_editor"])]
        return article


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")[:60] or "hsiyc-article"


def load_brief_file(path: str | Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Brief file not found: {path}")
    if path.suffix.lower() == ".json":
        return json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False, indent=1)
    return path.read_text(encoding="utf-8-sig")


def collect_photos(paths: Sequence[str | Path]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            out.extend(sorted(q for q in p.iterdir() if q.suffix.lower() in SUPPORTED_PHOTOS))
        elif p.suffix.lower() in SUPPORTED_PHOTOS:
            out.append(p)
    return out
