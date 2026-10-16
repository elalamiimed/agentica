"""Retrieval over the corpus of already-approved articles.

The strongest signal we have is the corpus itself, so instead of describing the
style only in the abstract we hand the model the most similar approved article as
a concrete exemplar. Retrieval is local and deterministic (character bigrams for
Chinese, word tokens for English) - no extra API calls, no embeddings service.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .config import CORPUS_DIR, PROJECT_DIR

WORK_DIR = PROJECT_DIR / "_work"

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN = re.compile(r"[a-z0-9]+")
_MAX_CHARS = 6000
# A real approved article is a full article. Anything this short is a fragment or a
# test file, and it must never become a style exemplar.
_MIN_CHARS = 1800


def _normalise(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _tokens(text: str) -> list[str]:
    """Character bigrams over CJK runs + latin words, so Chinese matches well."""
    norm = _normalise(text)
    tokens: list[str] = []
    cjk = "".join(_CJK.findall(norm))
    tokens.extend(cjk[i : i + 2] for i in range(max(0, len(cjk) - 1)))
    tokens.extend(_LATIN.findall(norm))
    return tokens


@dataclass
class CorpusDoc:
    slug: str
    title: str
    text: str
    kind: str = ""
    path: str = ""
    counts: Counter = field(default_factory=Counter)
    length: int = 0

    def score(self, query_counts: Counter) -> float:
        """Cosine similarity over the shared token space (cheap, no idf needed)."""
        if not self.counts or not query_counts:
            return 0.0
        shared = set(self.counts) & set(query_counts)
        dot = sum(self.counts[t] * query_counts[t] for t in shared)
        if not dot:
            return 0.0
        norm_a = math.sqrt(sum(v * v for v in self.counts.values()))
        norm_b = math.sqrt(sum(v * v for v in query_counts.values()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _kind_from_title(title: str) -> str:
    for marker, kind in (
        ("预告", "预告"),
        ("招募", "招募"),
        ("回顾", "回顾"),
        ("收官", "收官"),
        ("圆满", "收官"),
        ("斩获", "喜报"),
        ("讲堂", "讲堂"),
        ("竞赛", "竞赛"),
        ("嘉年华", "活动"),
        ("游园会", "活动"),
        ("学业支持", "学业支持"),
    ):
        if marker in title:
            return kind
    return "其他"


class Corpus:
    """Loads every approved article we have text for and can search it."""

    def __init__(self, docs: Iterable[CorpusDoc]):
        self.docs: list[CorpusDoc] = list(docs)

    def __len__(self) -> int:
        return len(self.docs)

    @classmethod
    def load(cls) -> "Corpus":
        docs: list[CorpusDoc] = []
        seen: set[str] = set()

        # Preferred: the structured index produced by the corpus analysis.
        index_path = WORK_DIR / "analysis" / "article_index.json"
        if index_path.is_file():
            try:
                for item in json.loads(index_path.read_text(encoding="utf-8")):
                    slug = (item.get("slug") or "").strip()
                    if slug and slug not in seen:
                        seen.add(slug)
            except (json.JSONDecodeError, TypeError):
                pass

        for txt in sorted((WORK_DIR).glob("*.txt")):
            text = txt.read_text(encoding="utf-8", errors="replace")
            if len(text) < _MIN_CHARS:
                continue
            slug = txt.stem
            title = next((ln.strip() for ln in text.splitlines() if ln.strip()), slug)
            docs.append(
                CorpusDoc(
                    slug=slug,
                    title=title,
                    text=text[:_MAX_CHARS],
                    kind=_kind_from_title(title),
                    path=str(txt),
                )
            )

        for extra_dir in (CORPUS_DIR,):
            if extra_dir.is_dir():
                for txt in sorted(extra_dir.glob("*.txt")):
                    text = txt.read_text(encoding="utf-8", errors="replace")
                    if len(text) < _MIN_CHARS:
                        continue
                    title = next((ln.strip() for ln in text.splitlines() if ln.strip()), txt.stem)
                    docs.append(
                        CorpusDoc(
                            slug=txt.stem,
                            title=title,
                            text=text[:_MAX_CHARS],
                            kind=_kind_from_title(title),
                            path=str(txt),
                        )
                    )

        for doc in docs:
            doc.counts = Counter(_tokens(doc.text))
            doc.length = len(doc.text)
        return cls(docs)

    # ------------------------------------------------------------------ search
    def search(self, query: str, k: int = 3, kind: str | None = None) -> list[tuple[CorpusDoc, float]]:
        qcounts = Counter(_tokens(query))
        ranked: list[tuple[CorpusDoc, float]] = []
        for doc in self.docs:
            score = doc.score(qcounts)
            if kind and doc.kind == kind:
                score *= 1.35  # prefer matching genre, never at the cost of irrelevance
            ranked.append((doc, score))
        ranked.sort(key=lambda pair: (-pair[1], pair[0].slug))
        return ranked[: max(1, k)]

    def by_slug(self, slug: str) -> CorpusDoc | None:
        for doc in self.docs:
            if doc.slug == slug:
                return doc
        return None

    def kinds(self) -> dict[str, int]:
        out: Counter = Counter(doc.kind for doc in self.docs)
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def truncate_for_prompt(text: str, max_chars: int = 3500) -> str:
    """Keep the head and the tail of an article - skeleton lives at both ends."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.75)]
    tail = text[-int(max_chars * 0.25) :]
    return f"{head}\n\n[...middle of the article omitted...]\n\n{tail}"
