"""Pre-submission validator - the reason articles stop coming back from the youth committee.

Every rule here exists because it is a way an HSIYC article can be sent back:
a Chinese paragraph with no English twin, a missing 三审 name, a half-width comma
in Chinese copy, a number that appears in the body but in nobody's brief, or a
headline that does not follow the house formula.

The validator is deterministic and offline: it costs no tokens and can be run by
the club on any draft, including drafts written by a human.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, Iterable, Sequence

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

ERROR, WARNING, INFO = "error", "warning", "info"

OFFICIAL_SIGNOFF_CN = "哈工大（深圳）国际青年俱乐部"
OFFICIAL_SIGNOFF_EN = "HITSZ International Youth Club"
CLUB_NEEDLES = ("哈工大（深圳）", "HITSZ", "HSIYC")
CREDIT_ROLES = ("文字", "图片", "排版", "一审", "二审", "三审")

PLACEHOLDER_PATTERNS = (
    r"^todo$", r"^tbd$", r"待定", r"待补", r"^xxx+$", r"^\?\?+$", r"^n/?a$",
    r"请填写", r"未定", r"placeholder", r"\[.*\]", r"<.*>", r"^—+$", r"^-+$",
)

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CJK_ONLY_TEXT = re.compile(r"^[\s\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff]+$")

# Chinese copy must not use these half-width marks.
HALFWIDTH_IN_CN = {",": "，", ";": "；", "?": "？", "!": "！", ":": "：", "(": "（", ")": "）"}
STRAIGHT_QUOTES = ('"', "'")

DATE_PATTERNS = (
    re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?"),
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*日"),
    re.compile(
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2}(?:\s*[–-]\s*\d{1,2})?,?\s*\d{4}",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{4}\b(?=\s*年)"),
)
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
STANDALONE_NUMBER_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])")

# Numbers spelled as words. A brief that says "a five-minute integral" whitelists
# the fact, but the article writes "5 分钟" - so a digits-only whitelist reports an
# invented number on perfectly good copy. Both spellings have to count.
_EN_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_EN_SCALES = {"hundred": 100, "thousand": 1000, "million": 1000000}
_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
_CN_NUMERAL_RE = re.compile(r"[零一二两三四五六七八九十百千万]+")


def _english_number_words(text: str) -> set[str]:
    """``a five-minute integral`` -> {'5'}; ``thirty-two`` -> {'32'}."""
    found: set[str] = set()
    total = 0
    open_run = False
    for word in re.findall(r"[a-z]+(?:-[a-z]+)*", text.lower()):
        value = None
        for part in word.split("-"):
            if part in _EN_UNITS:
                value = (value or 0) + _EN_UNITS[part]
            elif part in _EN_SCALES:
                value = max(value or 1, 1) * _EN_SCALES[part]
        if value is None:
            if open_run:
                found.add(str(total))
                total, open_run = 0, False
            continue
        total += value
        open_run = True
    if open_run:
        found.add(str(total))
    return found


def _chinese_number_words(text: str) -> set[str]:
    """``九十秒`` -> {'90'}; ``三十二名`` -> {'32'}."""
    found: set[str] = set()
    for run in _CN_NUMERAL_RE.findall(text):
        total, section, digit = 0, 0, None
        for char in run:
            if char in _CN_DIGITS:
                digit = _CN_DIGITS[char]
            elif char in _CN_UNITS:
                unit = _CN_UNITS[char]
                if unit >= 10000:
                    section = (section + (digit or 0)) * unit
                    total += section
                    section = 0
                else:
                    section += (digit if digit is not None else 1) * unit
                digit = None
        found.add(str(total + section + (digit or 0)))
    return found


def number_words(text: str) -> set[str]:
    """Every number in ``text``, however it is spelled."""
    return _english_number_words(text) | _chinese_number_words(text)


# Rank vocabulary, normalised to one key per prize. The brief may say "Champion"
# while the article says 冠军, so both spellings have to land on the same key or
# the attribution check compares nothing.
RANK_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("1", ("冠军", "第一名", "首位", "champion", "first place", "1st place", "gold medal")),
    ("2", ("亚军", "第二名", "runner-up", "runner up", "second place", "2nd place", "silver medal")),
    ("3", ("季军", "第三名", "third place", "3rd place", "bronze medal")),
    ("4", ("第四名", "fourth place", "4th place")),
    ("5", ("第五名", "fifth place", "5th place")),
    ("grand", ("特等奖", "grand prize", "grand award")),
    ("prize1", ("一等奖", "first prize", "first award")),
    ("prize2", ("二等奖", "second prize", "second award")),
    ("prize3", ("三等奖", "third prize", "third award")),
    ("excellent", ("优秀奖", "excellence award", "merit award")),
    ("special", ("特别奖", "special award")),
)
_RANK_LABELS = {"1": "冠军 (champion)", "2": "亚军 (runner-up)", "3": "季军 (third place)",
                "4": "第四名 (fourth place)", "5": "第五名 (fifth place)"}


def _rank_label(key: str) -> str:
    return _RANK_LABELS.get(key, key)


def _rank_key(label: str) -> str | None:
    """Normalise any rank spelling to one key, or None if it is not a rank."""
    low = str(label or "").strip().lower()
    if not low:
        return None
    for key, words in RANK_KEYS:
        if any(word in low for word in words):
            return key
    return None


def _name_tokens(value: str) -> set[str]:
    """A person's name in every form the article might write it.

    The brief stores 「谢昊轩 Xie Haoxuan」 and the article may print either half.
    """
    text = str(value or "").strip()
    if not text:
        return set()
    tokens = {text, text.lower()}
    cjk = "".join(char for char in text if "\u4e00" <= char <= "\u9fff")
    latin = " ".join(re.findall(r"[A-Za-z][A-Za-z'\-]+", text))
    if cjk:
        tokens.add(cjk)
    if latin:
        tokens.add(latin.lower())
        tokens.add(latin.lower().replace(" ", ""))
    return tokens


def _matches_any(name: str, candidates: set[str]) -> bool:
    tokens = _name_tokens(name)
    for candidate in candidates:
        if tokens & _name_tokens(candidate):
            return True
    return False


def _declared_ranks(brief: dict | None) -> dict[str, set[str]]:
    """``{'1': {'Tugsuu Rentsennatsag'}, '2': {...}}`` from the brief's winners list."""
    out: dict[str, set[str]] = {}
    if not isinstance(brief, dict):
        return out
    winners = brief.get("winners")
    if isinstance(winners, (str, dict)):
        winners = [winners]
    if not isinstance(winners, (list, tuple)):
        return out
    for entry in winners:
        if isinstance(entry, dict):
            rank = next((entry[key] for key in ("rank_cn", "rank_en", "rank", "place", "label")
                         if entry.get(key)), "")
            names = next((entry[key] for key in ("names", "name", "value", "winner", "who")
                          if entry.get(key)), "")
        else:
            text = str(entry)
            head, _, tail = text.partition(":")
            rank, names = (head, tail) if tail else (text, "")
        key = _rank_key(str(rank))
        if not key:
            continue
        for part in re.split(r"[、,，/／]| and |&", str(names)):
            part = part.strip()
            if part:
                out.setdefault(key, set()).add(part)
    return out


def _article_ranks(article: dict) -> dict[str, set[str]]:
    """Rank -> names as the article actually prints them, from its rank rows."""
    out: dict[str, set[str]] = {}
    for _, block in iter_body_blocks(article):
        if block.get("kind") != "list":
            continue
        for item in block.get("items") or []:
            key = _rank_key(str(item.get("label_cn") or "")) or _rank_key(str(item.get("label_en") or ""))
            if not key:
                continue
            for field in ("value_cn", "value_en"):
                for part in re.split(r"[、,，/／]| and |&", str(item.get(field) or "")):
                    part = part.strip()
                    if part:
                        out.setdefault(key, set()).add(part)
    return out


APEC_FRAMING = ("APEC", "亚太")

# Rank vocabulary the reviewers expect to see paired across languages.
RANK_PAIRS = (
    ("冠军", ("champion", "first place", "1st place")),
    ("亚军", ("runner", "second", "2nd")),
    ("季军", ("third", "3rd", "second runner")),
    ("第一名", ("first", "1st")),
    ("第二名", ("second", "2nd")),
    ("第三名", ("third", "3rd", "second runner")),
    ("第四名", ("fourth", "4th")),
    ("最佳代表", ("best delegate",)),
    ("杰出代表", ("outstanding delegate",)),
)

# People are named in the article in a small number of roles: with an honorific, or as
# a winner/participant in a ranking or name list. Rather than guessing at every surname
# (which matches ordinary words like 付出), collect names from those roles and check them
# against the material the operator supplied. That is exactly the shape of a fabricated
# winner - e.g. adding "特别奖 — 王梓涵 Wang Zihan" to an award list.
LATIN_NAME_RE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+)\b")
# A Chinese personal name starts with a surname. Requiring this is what keeps topic
# labels ("构图", "后期") and collective nouns ("不少同学", "各位老师") out of the
# fabricated-name check.
COMMON_SURNAMES = (
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾"
    "萧田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏"
    "韦付白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴"
    "莫孔汤常温康施文庞樊兰殷颜倪牛章鲁葛伍申尤毕聂焦柳骆祝纪梅盛童"
    "裴翁欧安辛靳管岳齐路涂乔霍隋晏瞿翟甘景卜祁蒲房牟滕岑解"
)
# Two-word surnames (欧阳, 司马, ...) so a four-character name still matches.
COMPOUND_SURNAMES = ("欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公孙", "慕容", "长孙")
SURNAME_NAME_RE = re.compile(
    rf"^(?:{'|'.join(COMPOUND_SURNAMES)}|[{COMMON_SURNAMES}])[\u4e00-\u9fff]{{1,2}}$"
)
# High-frequency characters that turn a surname-shaped token into an ordinary word
# (国家的, 师针对). Rejecting them keeps the fabricated-name check precise.
ORDINARY_CHARS = "的了是在有和与就都也很还要会能可以我们对这那一不没有为以于及等们个中上下前后之其所以因为"
# High-frequency words that begin with a surname character but are never names.
# These are rejected outright: "关注" (to pay attention) matched via surname 关 and
# "方便" via 方, both of which produced false positives in testing.
ORDINARY_WORDS = (
    "关注", "关心", "关于", "方便", "方向", "方式", "方面", "方才", "文章", "文化", "文字",
    "文明", "时间", "时候", "时机", "时代", "成果", "成绩", "成为", "成员", "国家", "国际",
    "国外", "国内", "团队", "团结", "解决问题", "解释", "解放", "和蔼", "和谐", "和平",
    "能力", "能够", "能源", "高兴", "高度", "高原", "直播", "直接", "直觉", "谢意", "谢谢",
    "友谊", "友情", "游乐", "游戏", "游客", "学习", "学校", "学生", "巩固", "固定", "计划",
    "计算", "设计", "相处", "相信", "相同", "相互", "面向", "目的", "目标", "师徒", "师兄",
    "师姐", "强调", "强项", "容纳", "容易", "容光", "从来", "从事", "从容", "都市", "都在",
    "都会", "了解", "了结", "方便面", "章节", "章程", "季节", "季军", "说明", "说话",
)
# Vocabulary that appears next to a name but is not part of one.
#
# The role words matter as much as the honorifics. A thank-you line reads
# 「感谢指导老师…」, which the surname pattern happily reads as a person called
# 谢指导 - a blocking error on perfectly good copy. Any word that can stand
# between 感谢/致谢 and 老师 belongs here.
NON_NAME_WORDS = (
    "同学", "老师", "教授", "大家", "各位", "我们", "他们", "参赛", "获奖", "选手",
    "指导", "评委", "主持", "嘉宾", "教练", "部长", "负责", "组织", "统筹", "志愿",
    "后勤", "宣传", "表演", "演出", "赞助", "支持", "配合", "筹备", "评审", "致辞",
)
# A Chinese name followed by its Latin form (谢昊轩 Xie Haoxuan) is approved usage,
# including inside an otherwise English field.
NAME_PAIR_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]{2,4}\s+[A-Za-z][A-Za-z.\- ]*$")


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    location: str = ""
    hint: str = ""

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "hint": self.hint,
        }

    def line(self) -> str:
        icon = {"error": "x", "warning": "!", "info": "i"}[self.severity]
        loc = f" [{self.location}]" if self.location else ""
        hint = f"\n      -> {self.hint}" if self.hint else ""
        return f"[{icon}] {self.code}: {self.message}{loc}{hint}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    checked: bool = True

    def add(self, code: str, severity: str, message: str, location: str = "", hint: str = "") -> None:
        self.findings.append(Finding(code, severity, message, location, hint))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == INFO]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def score(self) -> int:
        """0-100 readiness score, weighted so a missing 三审 name hurts a lot."""
        penalty = sum({"error": 14, "warning": 4, "info": 1}[f.severity] for f in self.findings)
        return max(0, 100 - penalty)

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.code))

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "score": self.score,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "infos": len(self.infos),
            "stats": self.stats,
            "findings": [f.as_dict() for f in self.sorted_findings()],
        }

    def text(self, title: str = "HSIYC pre-submission check") -> str:
        lines = [f"=== {title} ===", f"score {self.score}/100  -  {len(self.errors)} error(s), "
                 f"{len(self.warnings)} warning(s), {len(self.infos)} note(s)"]
        if self.ok:
            lines.append("RESULT: passes the structural/bilingual gate. A human still reads it before 送审.")
        else:
            lines.append("RESULT: NOT READY - fix the errors below before sending to the youth committee.")
        for bucket, header in ((ERROR, "ERRORS"), (WARNING, "WARNINGS"), (INFO, "NOTES")):
            items = [f for f in self.sorted_findings() if f.severity == bucket]
            if items:
                lines.append(f"\n-- {header} --")
                lines.extend(f.line() for f in items)
        if self.stats:
            lines.append("\n-- STATS --")
            lines.extend(f"{k}: {v}" for k, v in self.stats.items())
        return "\n".join(lines)


# --------------------------------------------------------------------------- helpers
# Characters that, when they appear immediately before/after a half-width mark, mean
# the mark belongs to a time, a ratio or a range rather than to Chinese prose.
_MARK_NEIGHBOURS = "0123456789:.-–—/%+~×xXN"


def _halfwidth_in_chinese(text: str, mark: str) -> bool:
    """True when a half-width mark sits inside running Chinese text.

    ``14:00-17:00``, ``1v1``, ``A509`` and ``18:30至21:00`` are all approved in the
    corpus, so a half-width mark is only a defect when it is genuinely surrounded by
    Chinese - and never when a digit or another time character abuts it.
    """
    if mark not in text:
        return False
    for match in re.finditer(re.escape(mark), text):
        before_char = text[match.start() - 1] if match.start() else ""
        after_char = text[match.end()] if match.end() < len(text) else ""
        if before_char in _MARK_NEIGHBOURS or after_char in _MARK_NEIGHBOURS:
            continue
        before = text[max(0, match.start() - 3) : match.start()]
        after = text[match.end() : match.end() + 3]
        if CJK.search(before) and CJK.search(after):
            return True
    return False


def is_blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def is_placeholder(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return True
    return any(re.search(pattern, text) for pattern in PLACEHOLDER_PATTERNS)


def han_count(text: str) -> int:
    return len(CJK.findall(text or ""))


def latin_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+", text or ""))


def iter_body_blocks(article: dict) -> Iterable[tuple[str, dict]]:
    for si, section in enumerate(article.get("sections") or [], 1):
        heading = section.get("heading_cn") or section.get("heading_en") or f"section {si}"
        for bi, block in enumerate(section.get("body") or [], 1):
            yield f"§{si} {heading} block{bi} ({block.get('kind')})", block


def collect_visible_text(article: dict) -> str:
    """Everything a reader will see, joined - used for style/format checks."""
    chunks: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in ("source", "file", "layout", "kind", "code"):
                    continue
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(article.get("title"))
    walk(article.get("lead"))
    walk(article.get("sections"))
    walk(article.get("closing"))
    walk(article.get("signoff"))
    walk(article.get("toc"))
    return "\n".join(chunks)


def collect_texts(article: dict) -> tuple[list[str], list[str]]:
    """Split the article into (chinese strings, english strings)."""
    cn: list[str] = []
    en: list[str] = []

    def walk(node: Any, key: str = "") -> None:
        if isinstance(node, str):
            if not node.strip():
                return
            target = None
            if key.endswith("_cn") or key == "cn":
                target = cn
            elif key.endswith("_en") or key == "en":
                target = en
            if target is not None:
                target.append(node)
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key)

    walk(article)
    return cn, en


def similar_to_corpus(
    text: str, corpus_texts: Sequence[str], threshold: float = 0.55
) -> list[tuple[int, float, str]]:
    """Sentence-level overlap against corpus articles - catches copy-paste drift.

    Whole-document Jaccard is too blunt: a passage lifted from a long approved
    article barely moves the ratio because the corpus document is large. Comparing
    sentence to sentence catches partial reuse, and lets the report name the exact
    sentence, which is far more actionable than a percentage.

    Returns ``[(corpus_index, score, draft_sentence), ...]`` - the best match per
    corpus article.
    """
    draft_sentences = _sentences(text)
    if not draft_sentences:
        return []
    draft_grams = [(_grams(s), s) for s in draft_sentences]
    hits: list[tuple[int, float, str]] = []
    for idx, other in enumerate(corpus_texts):
        corpus_grams = [_grams(s) for s in _sentences(other)]
        if not corpus_grams:
            continue
        worst = 0.0
        worst_sentence = ""
        for a, sentence in draft_grams:
            if not a:
                continue
            for b in corpus_grams:
                if not b or min(len(a), len(b)) < 8:  # too short to judge
                    continue
                jaccard = len(a & b) / len(a | b)
                if jaccard > worst:
                    worst, worst_sentence = jaccard, sentence
        if worst >= threshold:
            hits.append((idx, round(worst, 3), worst_sentence))
    return hits


def _grams(value: str) -> set[str]:
    compact = re.sub(r"\s+", "", value)
    return {compact[i : i + 2] for i in range(max(0, len(compact) - 1))}


def _sentences(text: str) -> list[str]:
    """Split on Chinese and English sentence enders, dropping fragments.

    Short spans are excluded on purpose: a stock bilingual heading such as
    "Award Winners:" is shared by definition, and flagging it as recycled copy
    would train the reader to ignore this check.
    """
    parts = re.split(r"[。！？；\n]+|(?<=[.!?])\s+", text or "")
    return [p.strip() for p in parts if len(re.sub(r"\s+", "", p.strip())) >= 14]


# --------------------------------------------------------------------------- the check
def validate(
    article: dict,
    *,
    brief: dict | None = None,
    allowed_numbers: set[str] | None = None,
    expected_photos: Sequence[str] = (),
    corpus_texts: Sequence[str] = (),
    corpus_labels: Sequence[str] = (),
    require_toc: bool = False,
    require_photos: bool = True,
) -> Report:
    """Run every pre-submission rule against one article object."""
    r = Report()
    if not isinstance(article, dict) or not article:
        r.add("SCHEMA-EMPTY", ERROR, "The article object is empty or not an object.")
        return r

    # Coerce obviously-wrong types to what the rules expect. A validator must always
    # return a report: crashing on a malformed draft is the one thing it cannot do,
    # because the caller then has no findings to act on.
    for key, expected, empty in (
        ("meta", dict, {}),
        ("title", dict, {}),
        ("lead", dict, {}),
        ("closing", dict, {}),
        ("signoff", dict, {}),
        ("credits", dict, {}),
        ("toc", dict, {}),
        ("sections", list, []),
        ("facts", list, []),
        ("needs_editor", list, []),
    ):
        value = article.get(key)
        if value is None:
            article[key] = empty
        elif not isinstance(value, expected):
            r.add(
                "SCHEMA-TYPE", ERROR,
                f"'{key}' should be a {expected.__name__}, found {type(value).__name__}.",
                key,
            )
            article[key] = empty

    for index, section in enumerate(article["sections"]):
        if not isinstance(section, dict):
            r.add("SCHEMA-TYPE", ERROR, f"Section {index + 1} is not an object.", f"sections[{index}]")
            article["sections"][index] = {}
            section = article["sections"][index]
        body = section.get("body")
        if body is None:
            section["body"] = []
        elif not isinstance(body, list):
            r.add("SCHEMA-TYPE", ERROR, f"Section {index + 1} body is not a list.", f"sections[{index}].body")
            section["body"] = []
        else:
            for bi, block in enumerate(body):
                if not isinstance(block, dict):
                    r.add("SCHEMA-TYPE", ERROR, f"Block {bi + 1} of section {index + 1} is not an object.", f"sections[{index}].body[{bi}]")
                    body[bi] = {"kind": "bilingual", "cn": "", "en": ""}
                elif block.get("items") is not None and not isinstance(block["items"], list):
                    r.add("SCHEMA-TYPE", ERROR, f"Block {bi + 1} of section {index + 1} has a non-list 'items'.", f"sections[{index}].body[{bi}]")
                    block["items"] = []
                elif block.get("photos") is not None and not isinstance(block["photos"], list):
                    r.add("SCHEMA-TYPE", ERROR, f"Block {bi + 1} of section {index + 1} has a non-list 'photos'.", f"sections[{index}].body[{bi}]")
                    block["photos"] = []

    title = article.get("title") or {}
    lead = article.get("lead") or {}
    sections = article.get("sections") or []
    closing = article.get("closing") or {}
    signoff = article.get("signoff") or {}
    credits = article.get("credits") or {}
    meta = article.get("meta") or {}

    # ---------------------------------------------------------------- structure
    for key, value in (("title", title), ("lead", lead), ("closing", closing),
                       ("signoff", signoff), ("credits", credits)):
        if not value:
            r.add("STRUCT-MISSING", ERROR, f"Required block '{key}' is missing.", key)

    if len(sections) < 6:
        r.add(
            "STRUCT-SECTIONS", ERROR,
            f"Only {len(sections)} section(s); approved articles run 8-13 (median 11), "
            "and an article this short reads as unfinished.",
            "sections",
            "Split the narrative into at least 6 sections, e.g. 活动背景 / 活动详情 / 精彩瞬间 / "
            "获奖名单 / 特别感谢 / 结语.",
        )
    if len(sections) > 14:
        r.add("STRUCT-LONG", WARNING, f"{len(sections)} sections is longer than any approved article.", "sections")

    # ---------------------------------------------------------------- bilingual parity
    if is_blank(title.get("cn")):
        r.add("BIL-TITLE", ERROR, "The Chinese headline is empty.", "title.cn")
    if is_blank(title.get("en")):
        r.add("BIL-TITLE", ERROR, "The English headline is empty.", "title.en")

    cn_title = (title.get("cn") or "").strip()
    if cn_title and "国际青年俱乐部" not in cn_title and "HSIYC" not in cn_title:
        r.add(
            "HEAD-FORMULA", WARNING,
            "The headline does not carry the club name.",
            "title.cn",
            'House formula: "国际青年俱乐部 | <类型词>：<主题>" (the "| HSIYC" tail is also accepted).',
        )
    if cn_title and not any(sep in cn_title for sep in ("|", "｜", "：", ":")):
        r.add(
            "HEAD-FORMULA", WARNING,
            "The headline has no ｜ or ： separator.",
            "title.cn",
            'Approved headlines look like "国际青年俱乐部 ｜无界青春：社团游园会圆满收官".',
        )

    for label, block in (("lead", lead), ("closing", closing)):
        if is_blank(block.get("cn")):
            r.add("BIL-BLOCK", ERROR, f"{label} has no Chinese text.", label + ".cn")
        if is_blank(block.get("en")):
            r.add("BIL-BLOCK", ERROR, f"{label} has no English text.", label + ".en")

    for si, section in enumerate(sections, 1):
        loc = f"sections[{si}]"
        if is_blank(section.get("heading_cn")):
            r.add("BIL-HEADING", ERROR, f"Section {si} has no Chinese heading.", loc + ".heading_cn")
        if is_blank(section.get("heading_en")):
            r.add("BIL-HEADING", ERROR, f"Section {si} has no English heading.", loc + ".heading_en")

        blocks = section.get("body") or []
        if not blocks:
            r.add("STRUCT-EMPTY", ERROR, f"Section {si} has no body.", loc)
        for bi, block in enumerate(blocks, 1):
            kind = block.get("kind")
            bloc = f"{loc}.body[{bi}]({kind})"
            if kind == "bilingual":
                if is_blank(block.get("cn")):
                    r.add("BIL-PARAGRAPH", ERROR, f"Chinese paragraph missing ({loc} #{bi}).", bloc)
                if is_blank(block.get("en")):
                    r.add(
                        "BIL-PARAGRAPH", ERROR,
                        f"Chinese paragraph has no English translation ({loc} #{bi}).",
                        bloc,
                        "Every CN paragraph needs its EN twin - this is the single most common return reason.",
                    )
                if not is_blank(block.get("cn")) and not is_blank(block.get("en")):
                    ratio = han_count(block["cn"]) / max(1, latin_word_count(block["en"]))
                    if ratio > 6 or ratio < 0.6:
                        r.add(
                            "BIL-RATIO", WARNING,
                            f"CN/EN length ratio is {ratio:.1f} for this paragraph; the corpus sits near 2-4 汉字 per English word.",
                            bloc,
                        )
            elif kind == "list":
                for ii, item in enumerate(block.get("items") or [], 1):
                    if is_blank(item.get("label_cn")) and is_blank(item.get("value_cn")):
                        r.add("LIST-EMPTY", ERROR, f"Empty list entry {ii} in {loc}.", bloc)
                    if (item.get("label_cn") or item.get("value_cn")) and not (
                        item.get("label_en") or item.get("value_en")
                    ):
                        r.add("BIL-LIST", WARNING, f"List entry {ii} has no English.", bloc)
            elif kind == "note":
                if is_blank(block.get("cn_note")) and is_blank(block.get("en_note")):
                    r.add("STRUCT-EMPTY", ERROR, f"Empty note block in {loc}.", bloc)
            elif kind == "photo_grid":
                if not block.get("photos"):
                    if require_photos:
                        r.add("PHOTO-EMPTY", WARNING, f"photo_grid with no photos in {loc}.", bloc)
            elif kind == "quote":
                if is_blank(block.get("cn")):
                    r.add("BIL-QUOTE", WARNING, f"Quote without Chinese text in {loc}.", bloc)
            elif kind not in ("divider",):
                r.add("SCHEMA-KIND", ERROR, f"Unknown block kind '{kind}'.", bloc)

    # ---------------------------------------------------------------- rank pairs
    all_cn, all_en = collect_texts(article)
    cn_blob = "\n".join(all_cn)
    en_blob = "\n".join(all_en).lower()
    for cn_rank, en_options in RANK_PAIRS:
        if cn_rank in cn_blob and not any(opt in en_blob for opt in en_options):
            r.add(
                "RANK-PAIR", WARNING,
                f"Chinese uses 「{cn_rank}」 but the English side never says "
                + " / ".join(f'"{opt}"' for opt in en_options) + ".",
                "list/rankings",
                "Winners must be titled in both languages, e.g. 冠军 / Champion.",
            )

    # ---------------------------------------------------------------- the 三审 block
    missing_roles: list[str] = []
    placeholder_roles: list[str] = []
    for role in CREDIT_ROLES:
        value = credits.get(role)
        if is_blank(value):
            missing_roles.append(role)
        elif is_placeholder(str(value)):
            placeholder_roles.append(role)

    if missing_roles:
        r.add(
            "CREDIT-MISSING", ERROR,
            "Credit block 三审 is incomplete; missing: " + "、".join(missing_roles),
            "credits",
            "The 三审 block must name 文字/图片/排版/一审/二审/三审 - approved articles always carry all six.",
        )
    if placeholder_roles:
        r.add(
            "CREDIT-PLACEHOLDER", ERROR,
            "Credit block contains placeholder text for: " + "、".join(placeholder_roles),
            "credits",
        )
    if not missing_roles and not placeholder_roles:
        # Separators are deliberately NOT checked: the corpus mixes ASCII comma,
        # full-width comma, 、 and bare spaces, and 7 of 12 club blocks mix two or
        # more inside one block. Only the role labels and the exact names matter.
        for role in ("一审", "二审", "三审"):
            names = [n for n in re.split(r"[、,，/／\s]+", str(credits.get(role, ""))) if n.strip()]
            limits = {"一审": 3, "二审": 3, "三审": 2}
            if len(names) > limits[role]:
                r.add(
                    "CREDIT-COUNT", WARNING,
                    f"{role} lists {len(names)} names; the corpus shows at most {limits[role]}.",
                    "credits." + role,
                )
            if not names:
                r.add("CREDIT-EMPTY", ERROR, f"{role} has no name.", "credits." + role)

    # ---------------------------------------------------------------- sign-off
    if not is_blank(signoff.get("cn")) and OFFICIAL_SIGNOFF_CN not in signoff["cn"]:
        r.add(
            "SIGNOFF-FORM", ERROR,
            f"Chinese sign-off should read exactly 「{OFFICIAL_SIGNOFF_CN}」.",
            "signoff.cn",
            f"Found: 「{signoff['cn'].strip()}」",
        )
    if not is_blank(signoff.get("en")) and OFFICIAL_SIGNOFF_EN.lower() not in signoff["en"].lower():
        r.add(
            "SIGNOFF-FORM", ERROR,
            f"English sign-off should read exactly 「{OFFICIAL_SIGNOFF_EN}」.",
            "signoff.en",
            f"Found: 「{signoff['en'].strip()}」",
        )

    visible = collect_visible_text(article)
    if not any(needle in visible for needle in CLUB_NEEDLES):
        r.add("CLUB-IDENTITY", WARNING, "The article never names the club.", "body")

    # ---------------------------------------------------------------- punctuation / formatting
    # Clock times (14:00-17:00) and short Latin spans use ASCII punctuation legitimately,
    # so a half-width mark only counts as a defect when Chinese characters surround it.
    for loc, block in iter_body_blocks(article):
        for field_name, value in block.items():
            if field_name not in ("cn", "caption_cn") or is_blank(value):
                continue
            for bad, good in HALFWIDTH_IN_CN.items():
                if _halfwidth_in_chinese(value, bad):
                    r.add(
                        "FORMAT-HALFWIDTH", WARNING,
                        f"Half-width '{bad}' inside Chinese copy; use '{good}'.",
                        f"{loc}.{field_name}",
                        value.strip()[:80],
                    )
                    break
            for q in STRAIGHT_QUOTES:
                if q in value and CJK.search(value):
                    r.add(
                        "FORMAT-QUOTE", WARNING,
                        "Straight quote inside Chinese copy; use “ ” or 「 」.",
                        f"{loc}.{field_name}",
                        value.strip()[:80],
                    )
                    break

    for i, cn_text in enumerate(all_cn, 1):
        for bad, good in HALFWIDTH_IN_CN.items():
            if _halfwidth_in_chinese(cn_text, bad):
                r.add("FORMAT-HALFWIDTH", WARNING, f"Half-width '{bad}' in Chinese text; use '{good}'.", f"cn#{i}", cn_text.strip()[:80])
                break
    for i, en_text in enumerate(all_en, 1):
        # 谢昊轩 Xie Haoxuan is approved usage, not a translation error.
        if CJK.search(en_text) and not NAME_PAIR_RE.match(en_text.strip()):
            r.add(
                "FORMAT-CJK-IN-EN", WARNING,
                "Chinese characters inside an English field (other than a name pair).",
                f"en#{i}",
                en_text.strip()[:80],
            )
        # A purely Latin string is fine as-is; only flag CJK punctuation next to CJK text.
        if CJK.search(en_text) and re.search(r"[，。、；：（）“”]", en_text):
            r.add("FORMAT-CN-PUNCT-IN-EN", WARNING, "Chinese punctuation inside English copy.", f"en#{i}", en_text.strip()[:80])

    for i, cn_text in enumerate(all_cn, 1):
        if re.search(r"[A-Za-z]\d|\d[A-Za-z]", cn_text):
            r.add("FORMAT-SPACING", INFO, "Latin/number adjacency in Chinese copy - check a space is intended.", f"cn#{i}", cn_text.strip()[:60])

    total_cn = sum(han_count(t) for t in all_cn)
    total_en = sum(latin_word_count(t) for t in all_en)
    # Corpus: 305-2,261 CN body characters over 13 text-complete articles, median 860.
    # The style contract asks a new article for 700-1,400; below that it reads unfinished.
    if total_cn < 700:
        r.add(
            "LEN-SHORT", ERROR,
            f"Only {total_cn} Chinese characters of body copy; the house target is 700-1,400 "
            "(approved articles run 305-2,261, median 860).",
            "body",
            "Expand with detail that is already in the brief: venue, format, schedule, counts, "
            "who did what. Do not pad with repetition.",
        )
    elif total_cn < 800:
        r.add("LEN-SHORT", WARNING, f"{total_cn} Chinese characters - just under the 700-1,400 target band.", "body")
    if total_cn > 3000:
        r.add("LEN-LONG", INFO, f"{total_cn} Chinese characters - longer than any approved article.", "body")
    if total_en and total_cn:
        ratio = total_cn / total_en
        # Corpus ratio: 1.73 mean, 1.79 median, range 1.18-2.26.
        if ratio < 1.0 or ratio > 3.2:
            r.add(
                "LEN-RATIO", WARNING,
                f"CN:EN ratio is {ratio:.2f}; the approved corpus sits at 1.73-1.79 (range 1.18-2.26).",
                "body",
                "One language looks like a summary of the other rather than a mirror.",
            )

    # ---------------------------------------------------------------- facts
    facts = article.get("facts") or []
    dates_from_meta = " ".join(_iter_scalars(meta))
    sourced = " ".join(str(f.get("source", "")) for f in facts if isinstance(f, dict))
    unknown_facts = [
        f.get("fact", "") for f in facts
        if isinstance(f, dict) and str(f.get("source", "")).strip().lower() in ("", "unknown", "guess", "assumed")
    ]
    if unknown_facts:
        r.add(
            "FACT-UNSOURCED", ERROR,
            f"{len(unknown_facts)} fact(s) have no source: " + "; ".join(map(str, unknown_facts[:4])),
            "facts",
            "Every concrete claim must trace to the brief or to a photo. Remove it or list it under needs_editor.",
        )
    if not facts:
        r.add(
            "FACT-NONE", WARNING,
            "No facts were declared, so the body cannot be cross-checked for invented details.",
            "facts",
        )
    if "corpus:" in sourced:
        r.add(
            "FACT-CORPUS-LEAK", WARNING,
            "A 'fact' is sourced from a previous article, not from this event - make sure it is not last year's detail.",
            "facts",
        )

    # Numbers in the body that appear in no brief / date.
    body_numbers = set(STANDALONE_NUMBER_RE.findall(cn_blob)) | set(STANDALONE_NUMBER_RE.findall(en_blob))
    brief_numbers: set[str] = set()
    # Only material the OPERATOR supplied may whitelist a number. The article's own
    # "facts" list must not: otherwise the model can invent a figure, declare it,
    # and pass its own check.
    for source in ((brief or {}), {"credits": credits}, meta, {"date": dates_from_meta}):
        for value in _iter_scalars(source):
            brief_numbers |= set(STANDALONE_NUMBER_RE.findall(value))
            brief_numbers |= number_words(value)
    if allowed_numbers:
        brief_numbers |= {str(n) for n in allowed_numbers}
    if brief is None:
        r.add(
            "FACT-NO-BRIEF", WARNING,
            "No brief was supplied, so numbers and names cannot be traced to their source.",
            "facts",
            "Pass the brief with -b/--brief to check the article against the material it came from.",
        )
    unexplained = {n for n in body_numbers - brief_numbers}
    noise = {"1", "2", "3", "01", "02", "03"}
    unexplained -= noise
    if unexplained:
        r.add(
            "FACT-NUMBER", ERROR,
            "These numbers appear in the body but in no supplied material: "
            + ", ".join(sorted(unexplained)[:12]),
            "body",
            "An invented score, count or date is a guaranteed return. Add the number to the brief or delete it.",
        )

    # ---------------------------------------------------------------- rank attribution
    # Knowing a name is not the same as knowing WHERE it belongs. A swapped champion
    # and runner-up, or a gold medal moved to fourth place, used to pass this check
    # untouched - and naming the wrong winner is the single error most likely to get
    # an article returned, because the winner reads it.
    declared_ranks = _declared_ranks(brief)
    if declared_ranks:
        for row_rank, row_names in _article_ranks(article).items():
            if row_rank not in declared_ranks:
                continue
            expected = declared_ranks[row_rank]
            for name in row_names:
                if _matches_any(name, expected):
                    continue
                # The name may be real but filed under the wrong rank.
                elsewhere = next((rank for rank, names in declared_ranks.items()
                                  if rank != row_rank and _matches_any(name, names)), "")
                if elsewhere:
                    r.add(
                        "FACT-RANK", ERROR,
                        f"「{name}」 is listed under {_rank_label(row_rank)} but the brief "
                        f"declares it for {_rank_label(elsewhere)}.",
                        "body",
                        "A winner reading their own name against the wrong prize is the fastest "
                        "route to a correction. Match the rank to the brief.",
                    )

    # Named people are the other half of the hallucination risk. Flag any personal
    # name in the body that appears in neither the brief nor the credits - a
    # fabricated winner or judge is the classic way an article gets returned.
    source_text = " ".join(_iter_scalars(brief or {})) + " " + " ".join(_iter_scalars(credits))
    source_text += " " + " ".join(_iter_scalars(article.get("title"))) + " " + dates_from_meta
    source_lower = source_text.lower()
    known = set(re.findall(r"[\u4e00-\u9fff]{2,6}", source_text))

    def is_known_cn(name: str) -> bool:
        return name in known or any(name in k or k in name for k in known if len(k) >= 2)

    suspicious: list[str] = []
    # Scan every surname-shaped name immediately followed by an honorific. Anchoring on
    # the surname pattern (rather than a greedy capture) keeps 「不同国家的同学」 out, but
    # a verb can still precede a real name - 「感谢凌怡老师」 starts with the surname 谢.
    # So for each match, try progressively shorter readings and accept the first one the
    # material already knows; only an unreadable match is reported.
    for match in re.finditer(
        rf"(?:{'|'.join(COMPOUND_SURNAMES)}|[{COMMON_SURNAMES}])[\u4e00-\u9fff]{{1,3}}"
        r"(?=老师|教授|博士|同学|先生|女士|主席|队长)",
        cn_blob,
    ):
        raw = match.group(0)
        if any(ch in raw for ch in ORDINARY_CHARS) or any(raw in word for word in ORDINARY_WORDS):
            continue
        if any(word in raw for word in NON_NAME_WORDS):
            continue
        readings = [raw[i:] for i in range(0, max(1, len(raw) - 1))]
        if any(is_known_cn(reading) for reading in readings):
            continue
        shaped = [
            r for r in readings
            if SURNAME_NAME_RE.fullmatch(r) and not any(word in r for word in NON_NAME_WORDS)
        ]
        if shaped:
            suspicious.append(shaped[-1])
    # Names carried by a ranking or participant list. A list item may hold a topic
    # label or a course name as easily as a person, so both a name SHAPE test
    # (surname, or proper-noun capitalisation) and the source-text test must pass.
    for _, block in iter_body_blocks(article):
        if block.get("kind") != "list":
            continue
        for item in block.get("items") or []:
            for field in ("value_cn", "value_en"):
                for part in re.split(r"[、,，/／]| - | – |：|:", str(item.get(field) or "")):
                    part = part.strip()
                    if len(part) < 2 or any(word in part for word in NON_NAME_WORDS):
                        continue
                    if SURNAME_NAME_RE.fullmatch(part) and len(part) >= 3:
                        # A 3+ character surname-shaped token in a ranking row is a
                        # name. Two-character tokens are not reliable (国家的), and a
                        # fabricated award name is longer than that anyway.
                        if not is_known_cn(part):
                            suspicious.append(part)
                    elif LATIN_NAME_RE.fullmatch(part) and part.lower() not in source_lower:
                        suspicious.append(part)

    # Surname matching is fuzzy, so only report names that look like a person and are
    # absent from the material; dedupe and cap the list.
    suspicious = sorted({s for s in suspicious if len(s) >= 2})
    if suspicious:
        r.add(
            "FACT-NAME", ERROR,
            "These people are named in the article but appear in neither the brief nor the credits: "
            + "、".join(suspicious[:8]),
            "body",
            "Never invent a person. Add the name to the brief (winner, judge, speaker, organiser) or remove it.",
        )

    # Dates must be consistent between the two languages.
    cn_dates = _dates_in(cn_blob)
    en_dates = _dates_in(en_blob)
    if cn_dates and en_dates and not _dates_agree(cn_dates, en_dates):
        r.add(
            "FACT-DATE-MISMATCH", WARNING,
            f"Chinese and English date mentions differ: CN={sorted(cn_dates)} EN={sorted(en_dates)}.",
            "body",
        )

    # ---------------------------------------------------------------- CN/EN fact parity
    # "EN may compress, but must add no fact." The corpus itself drifts in places, so
    # this is graded as a warning rather than blocked.
    cn_numbers = {n for n in STANDALONE_NUMBER_RE.findall(cn_blob)}
    en_numbers = {n for n in STANDALONE_NUMBER_RE.findall(en_blob)}
    en_only = {n for n in en_numbers - cn_numbers if len(n) > 1 or True} - {"1", "2", "3"}
    if en_only:
        r.add(
            "BIL-FACT-EN-ONLY", WARNING,
            "These numbers appear only in the English copy: " + ", ".join(sorted(en_only)[:10]),
            "body",
            "EN may compress CN, but a number that exists only in EN is a fact the reviewers cannot "
            "verify against the Chinese text.",
        )

    # ---------------------------------------------------------------- phase / tense
    # Only the prose counts: the headline of a recap legitimately contains 回顾, so
    # checking the whole visible text would make this rule fire on every article.
    phase = str(meta.get("doc_type", ""))
    prose_cn = _article_prose(article)
    recap_markers = ("圆满落幕", "圆满举行", "成功举办", "已经结束", "落下帷幕")
    preview_markers = ("即将启幕", "即将举行", "敬请期待", "请扫描", "快来加入", "报名从速", "踊跃报名")
    if phase in ("回顾", "收官", "喜报"):
        hits = [m for m in preview_markers if m in prose_cn]
        if hits and not any(m in prose_cn for m in recap_markers):
            r.add(
                "TYPE-PHASE", WARNING,
                f"This is a {phase} but the copy uses preview language: " + "、".join(hits),
                "body",
                "A recap must speak in the perfective (圆满落幕/成功举办); a preview must not.",
            )
    elif phase in ("预告", "招募"):
        hits = [m for m in recap_markers if m in prose_cn]
        if hits:
            r.add(
                "TYPE-PHASE", WARNING,
                f"This is a {phase} but the copy uses recap language: " + "、".join(hits),
                "body",
                "A preview must not announce that the event already concluded.",
            )

    # ---------------------------------------------------------------- photos
    grid_photos: list[str] = []
    for _, block in iter_body_blocks(article):
        if block.get("kind") == "photo_grid":
            for photo in block.get("photos") or []:
                name = str(photo.get("file", "")).strip()
                if name:
                    grid_photos.append(name)
                else:
                    r.add("PHOTO-NONAME", WARNING, "A photo entry has no file name.", "photo_grid")
    duplicates = {n for n in grid_photos if grid_photos.count(n) > 1}
    if duplicates:
        r.add("PHOTO-DUPLICATE", WARNING, "The same photo is placed more than once: " + ", ".join(sorted(duplicates)), "photo_grid")
    # The brief mentioning photos while none were supplied is the common
    # "operator forgot the attachments" case, and it must not pass silently.
    brief_mentions_photos = bool(
        re.search(r"照片|图片|合影|photo|image|picture", " ".join(_iter_scalars(brief or {})), re.IGNORECASE)
    )
    if require_photos and brief_mentions_photos and not grid_photos:
        r.add(
            "PHOTO-MENTIONED", WARNING,
            "The brief refers to photos, but none were supplied, so the article has no photo block.",
            "photo_grid",
            "Upload the photos (or pass -p) so the agent can place and caption them; approved articles "
            "almost always carry at least one.",
        )
    if expected_photos:
        expected = {str(n) for n in expected_photos}
        unused = expected - set(grid_photos)
        missing = set(grid_photos) - expected
        if unused:
            r.add(
                "PHOTO-UNUSED", WARNING,
                f"{len(unused)} uploaded photo(s) are never placed: " + ", ".join(sorted(unused)),
                "photo_grid",
            )
        if missing:
            r.add(
                "PHOTO-UNKNOWN", ERROR,
                "The article places photos that were not uploaded: " + ", ".join(sorted(missing)),
                "photo_grid",
            )
        if require_photos and not grid_photos:
            r.add("PHOTO-NONE", ERROR, "No photos are placed anywhere; approved articles always carry photo blocks.", "photo_grid")

    # ---------------------------------------------------------------- house extras
    if require_toc and not (article.get("toc") or {}).get("previous") and not (article.get("toc") or {}).get("next"):
        r.add("TOC-MISSING", WARNING, "The 精彩回顾 · Table of Contents card has no previous/next article.", "toc")

    if meta.get("doc_type") in ("预告", "招募"):
        if not any(word in visible for word in APEC_FRAMING):
            r.add(
                "TYPE-FRAMING", INFO,
                "This is a 预告/招募 and the approved ones usually open with the APEC / 亚太 framing.",
                "lead",
            )
    closing_cn = str(closing.get("cn", ""))
    if len(sections) >= 3 and "感谢" not in cn_blob and "谢谢" not in cn_blob:
        r.add("TONE-THANKS", INFO, "No acknowledgement anywhere; approved articles thank participants, judges or partners.", "body")
    if "特别感谢" in cn_blob and "special thanks" not in en_blob:
        r.add("BIL-THANKS", WARNING, "「特别感谢」 has no \"Special Thanks\" English counterpart.", "body")

    # ---------------------------------------------------------------- similarity to corpus
    if corpus_texts:
        hits = similar_to_corpus(_article_prose(article), corpus_texts)
        for idx, jac, sentence in hits:
            label = corpus_labels[idx] if idx < len(corpus_labels) else f"corpus[{idx}]"
            # Reusing one article's sentence is normal club practice, especially when
            # covering the same event or series (the approved series posts share
            # phrasing deliberately). A sentence that recurs across SEVERAL different
            # approved articles is generic filler, and that is what gets blocked.
            shared = sum(1 for _, other, text in hits if _grams(text) == _grams(sentence))
            severity = ERROR if (jac >= 0.99 and shared >= 2) else WARNING
            excerpt = sentence if len(sentence) <= 90 else sentence[:90] + "…"
            if shared >= 2:
                hint = (
                    f"This phrasing also appears in {shared} different approved articles, which means "
                    "it is generic filler - reword it."
                )
            else:
                hint = (
                    "Overlap with one approved article is expected when this covers the same event or "
                    "series; confirm it is intentional, otherwise reword it."
                )
            r.add(
                "SIMILARITY", severity,
                f"This sentence is {jac:.0%} identical to one in '{label}': 「{excerpt}」",
                "body",
                hint,
            )

    # ---------------------------------------------------------------- editor handover
    needs = article.get("needs_editor") or []
    if not needs:
        r.add(
            "HANDOVER-EMPTY", INFO,
            "needs_editor is empty - unusual: confirm no name, number, photo credit or 三审 name is outstanding.",
            "needs_editor",
        )
    else:
        r.add("HANDOVER", INFO, f"{len(needs)} item(s) for the human editor: " + "; ".join(map(str, needs[:6])), "needs_editor")

    r.stats = {
        "sections": len(sections),
        "chinese_characters": total_cn,
        "english_words": total_en,
        "cn_per_en_word": round(total_cn / total_en, 2) if total_en else None,
        "photos_placed": len(grid_photos),
        "facts_declared": len(facts),
        "body_numbers": len(body_numbers),
        "credit_roles_filled": sum(1 for role in CREDIT_ROLES if not is_blank(credits.get(role))),
        "doc_type": meta.get("doc_type", ""),
    }
    return r


# --------------------------------------------------------------------------- internals
def _iter_scalars(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _iter_scalars(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_scalars(item)
    elif isinstance(node, (int, float)):
        yield str(node)


def _article_prose(article: dict) -> str:
    """Body copy only - used for corpus-similarity, excluding credits and meta."""
    parts: list[str] = []
    lead = article.get("lead") or {}
    parts += [lead.get("cn", ""), lead.get("en", "")]
    for section in article.get("sections") or []:
        for block in section.get("body") or []:
            for key in ("cn", "en"):
                if isinstance(block.get(key), str):
                    parts.append(block[key])
    closing = article.get("closing") or {}
    parts += [closing.get("cn", ""), closing.get("en", "")]
    return "\n".join(p for p in parts if p)


def _dates_in(text: str) -> set[str]:
    found: set[str] = set()
    for pattern in DATE_PATTERNS:
        for match in pattern.findall(text):
            if isinstance(match, tuple):
                match = "".join(match)
            found.add(re.sub(r"\s+", "", str(match)))
    return found


# The canonical date model, shared by the intake form (does the description mention a day
# that is not the event date?) and by the description developer (did the rewrite move a
# date?). It is deliberately richer than DATE_PATTERNS, which the article check uses for
# its own purposes: an operator writing notes has no obligation to include the year, and
# writes "8 november" as readily as "11月8日".
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    # Abbreviations are safe because every pattern requires a digit beside the month.
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_WORDS = "|".join(sorted(_MONTHS, key=len, reverse=True))
_MONTH_TITLES = "|".join(sorted({m.capitalize() for m in _MONTHS}, key=len, reverse=True))
_MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# ８ etc. Full-width digits are what a Chinese IME produces, and an operator told they
# invented their own headcount because they typed ３２ instead of 32 would rightly stop
# trusting the check. The translation is 1:1, so every index stays valid.
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

_SPAN_DATE_PATTERNS = (
    # 11月8日至9日 / 11月8日、9日 / 11月8-9日 / 2026年11月8日至9日
    re.compile(r"(?:(?P<y>\d{4})\s*年\s*)?(?P<m>\d{1,2})\s*月\s*(?P<d1>\d{1,2})(?!\d)\s*[日号]?"
               r"\s*(?:至|到|~|～|—|–|－|-|、|,)\s*(?P<d2>\d{1,2})(?![\d月])\s*[日号]?"),
    # 8-9 November / 8 to 9 November / 8th to 9th of November 2026
    re.compile(rf"(?P<d1>\d{{1,2}})(?!\d)(?:st|nd|rd|th)?\s*"
               r"(?:至|到|~|～|—|–|－|-|to|through|and)\s*"
               rf"(?P<d2>\d{{1,2}})(?!\d)(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mon>{_MONTH_WORDS})\b\.?"
               r"(?:\s*,?\s*(?P<y>\d{4}))?", re.IGNORECASE),
    # November 8-9 / November 8 to 9, 2026
    re.compile(rf"\b(?P<mon>{_MONTH_TITLES})\b\.?\s+(?P<d1>\d{{1,2}})(?!\d)(?:st|nd|rd|th)?\s*"
               r"(?:至|到|~|～|—|–|－|-|to|through|and)\s*(?P<d2>\d{1,2})(?!\d)(?:st|nd|rd|th)?"
               r"(?:\s*,?\s*(?P<y>\d{4}))?"),
    # 2026年11月8日 / 11月8日 / 11月8号
    re.compile(r"(?:(?P<y>\d{4})\s*年\s*)?(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})(?!\d)\s*[日号]"),
    # 2026-11-08 / 2026/11/8 / 2026.11.8
    re.compile(r"(?P<y>\d{4})\s*[-/.]\s*(?P<m>\d{1,2})\s*[-/.]\s*(?P<d>\d{1,2})(?!\d)"),
    # 8 November / 8th of November 2026 / 8 nov
    re.compile(rf"(?P<d>\d{{1,2}})(?!\d)(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mon>{_MONTH_WORDS})\b\.?"
               r"(?:\s*,?\s*(?P<y>\d{4}))?", re.IGNORECASE),
    # November 8, 2026 - only a capitalised month: "we march 5 kilometres" is a verb, and
    # reading it as 5 March turned a faithful rewrite into an invented figure.
    re.compile(rf"\b(?P<mon>{_MONTH_TITLES})\b\.?\s+(?P<d>\d{{1,2}})(?!\d)(?:st|nd|rd|th)?"
               r"(?:\s*,?\s*(?P<y>\d{4}))?"),
    # november 8, 2026 - a lowercase month first needs the year to be a date at all
    re.compile(rf"\b(?P<mon>{_MONTH_WORDS})\b\.?\s+(?P<d>\d{{1,2}})(?!\d)(?:st|nd|rd|th)?"
               r"\s*,?\s*(?P<y>\d{4})", re.IGNORECASE),
)


def normalise_digits(text: str) -> str:
    """Full-width digits as ASCII, without moving a single index."""
    return (text or "").translate(_FULLWIDTH_DIGITS)


def _valid_day(month: int, day: int, year: str | None = None) -> bool:
    """A real calendar day. Without a year, 29 February is allowed rather than argued with."""
    if not 1 <= month <= 12 or day < 1:
        return False
    if year:
        try:
            _date(int(year), month, day)
            return True
        except ValueError:
            return False
    return day <= _MONTH_DAYS[month - 1]


def canonical_dates(text: str) -> tuple[set[str], list[tuple[int, int]]]:
    """Dates in ``text``, as ``YYYY-MM-DD`` (year given) or ``MM-DD`` (year omitted).

    Ranges count as both of their days: 11月8日至9日 and "8 to 9 November" are the same
    two dates, and reading only the first left the second day's digit looking invented.

    Also returns the character spans of each date's month and day, so a caller comparing
    digits can blank them: the "11" of 11月8日 is a part of a date, not a new number. A
    year is deliberately *not* blanked - "8 November" rewritten as "2026年11月8日" adds a
    year the operator never wrote, and that is worth reporting.
    """
    found: set[str] = set()
    blanks: list[tuple[int, int]] = []
    claimed: list[tuple[int, int]] = []

    text = normalise_digits(text)
    candidates = [match for pattern in _SPAN_DATE_PATTERNS for match in pattern.finditer(text)]
    # Longest match at a position wins, so 2026年11月8日 is not also read as 11月8日.
    for match in sorted(candidates, key=lambda m: (m.start(), -(m.end() - m.start()))):
        if any(match.start() < end and start < match.end() for start, end in claimed):
            continue
        groups = match.groupdict()
        try:
            month = int(groups["m"]) if groups.get("m") else _MONTHS[(groups.get("mon") or "").lower()]
        except (KeyError, TypeError, ValueError):
            continue
        days: list[int] = []
        for name in ("d", "d1", "d2"):
            raw = groups.get(name)
            if raw is None:
                continue
            try:
                days.append(int(raw))
            except ValueError:  # pragma: no cover - the groups are \d+
                continue
        year = groups.get("y")
        if not days or not all(_valid_day(month, day, year) for day in days):
            continue
        claimed.append((match.start(), match.end()))
        for day in days:
            found.add(f"{int(year):04d}-{month:02d}-{day:02d}" if year else f"{month:02d}-{day:02d}")
        for group in ("m", "mon", "d", "d1", "d2"):
            if group not in groups:
                continue
            span = match.span(group)
            if span[0] >= 0:
                blanks.append(span)
    return found, blanks


def _dates_agree(cn_dates: set[str], en_dates: set[str]) -> bool:
    """True when the two languages reference overlapping day numbers."""
    def days(values: set[str]) -> set[str]:
        out: set[str] = set()
        for value in values:
            out |= set(re.findall(r"\d{1,2}", value))
        return out

    cn_days, en_days = days(cn_dates), days(en_dates)
    if not cn_days or not en_days:
        return True
    return bool(cn_days & en_days)
