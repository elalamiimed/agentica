"""Map an event to a visual identity.

This is the "vibes" half of the artwork: given the text of an article (title,
lead, sections, venue, doc type), decide what the picture should look like -
which palette, which motif, which mood - and produce an English prompt for the
optional AI image backend.

The rules are data, not code. ``spec/ART_SPEC.md`` documents them for the club,
and ``classify`` returns the evidence it used, so the UI can explain *why* a
given event came out indigo-and-amber rather than asking anyone to trust it.

Matching is deliberately boring: presence of a keyword, weighted by how specific
the keyword is. A club member can read the table and predict the result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- model
@dataclass(frozen=True)
class Vibe:
    key: str
    label_cn: str
    label_en: str
    motif: str
    background: str
    primary: str
    accent: str
    secondary: str
    ink: str
    mood_cn: str
    mood_en: str
    scene_en: str
    keywords: tuple[str, ...] = ()
    default_background: str = "deep"

    @property
    def palette(self) -> dict[str, str]:
        return {
            "background": self.background,
            "primary": self.primary,
            "accent": self.accent,
            "secondary": self.secondary,
            "ink": self.ink,
        }

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label_cn": self.label_cn,
            "label_en": self.label_en,
            "motif": self.motif,
            "mood_cn": self.mood_cn,
            "mood_en": self.mood_en,
            "palette": self.palette,
            "prompt_scene": self.scene_en,
            "default_background": self.default_background,
        }


# Shared style anchor. Keeping it identical across every vibe is what makes a
# set of club posters look like one family instead of twelve stock images.
STYLE_EN = (
    "flat vector editorial illustration, bold geometric shapes, limited palette, "
    "soft paper grain, cinematic side lighting, generous negative space, "
    "clean modern poster art, absolutely no text, no letters, no words, "
    "no numbers, no logos, no watermark, no signature"
)
NEGATIVE_EN = "text, letters, typography, watermark, signature, logo, cluttered, noisy, low contrast"

VIBES: tuple[Vibe, ...] = (
    Vibe(
        key="photography", label_cn="摄影影像", label_en="Photography & film", motif="aperture",
        background="#0B1220", primary="#1B3870", accent="#E8B04B", secondary="#3E8E9C", ink="#F4F6FA",
        mood_cn="光影、构图、记录", mood_en="Light, framing, memory",
        scene_en="a large camera aperture iris built from overlapping blades with light rays passing through it",
        keywords=("摄影", "拍照", "相机", "镜头", "光影", "快门", "照片", "photo", "photograph",
                  "photography", "camera", "lens", "shutter", "portrait"),
    ),
    Vibe(
        key="sports", label_cn="体育竞技", label_en="Sports & competition", motif="shuttle",
        background="#0C1A2E", primary="#14315E", accent="#FF7A3D", secondary="#2EC4A6", ink="#F7FAFF",
        mood_cn="速度、对抗、团队", mood_en="Speed, contest, teamwork",
        scene_en="a badminton shuttlecock caught mid-flight with sweeping motion arcs and speed trails",
        keywords=("羽毛球", "篮球", "足球", "乒乓球", "网球", "排球", "运动", "体育", "球赛", "友谊赛",
                  "健身", "联赛", "赛事", "比赛", "badminton", "basketball", "football", "soccer",
                  "tennis", "volleyball", "sports", "tournament", "fitness", "athletics"),
    ),
    Vibe(
        key="culture", label_cn="文化传统", label_en="Culture & tradition", motif="lantern",
        background="#23102F", primary="#3B1D52", accent="#E8B04B", secondary="#C8392B", ink="#FBF3E4",
        mood_cn="传统、多元、世界", mood_en="Heritage, diversity, the world",
        scene_en="hanging paper lanterns, silk ribbons and a curved arc of stylised continents",
        keywords=("文化", "传统", "手艺", "民俗", "非遗", "汉服", "书法", "茶艺", "文化节", "美食节",
                  "美食", "手工艺", "世界传统", "culture", "cultural", "traditional", "craft",
                  "heritage", "festival", "cuisine"),
    ),
    Vibe(
        key="study", label_cn="学业支持", label_en="Study & academic support", motif="study",
        background="#0E2740", primary="#143A5E", accent="#6FD3C7", secondary="#F0C987", ink="#F2F7FB",
        mood_cn="专注、互助、成长", mood_en="Focus, peer support, progress",
        scene_en="a neat stack of books beside an open notebook and a pencil under a soft lamp glow",
        keywords=("学业", "学习", "考试", "期末", "期中", "辅导", "答疑", "讲座", "讲堂", "沙龙",
                  "分享会", "自习", "备考", "复习", "study", "exam", "final", "tutorial", "lecture",
                  "seminar", "academic", "tutoring", "revision", "workshop"),
    ),
    Vibe(
        key="award", label_cn="荣誉喜报", label_en="Awards & honours", motif="trophy",
        background="#131A33", primary="#1B3870", accent="#F2C14E", secondary="#B3253A", ink="#FFF8E7",
        mood_cn="荣耀、突破、祝贺", mood_en="Honour, breakthrough, congratulations",
        scene_en="a laurel wreath and trophy silhouette with a burst of confetti and light rays",
        keywords=("喜报", "获奖", "斩获", "大奖", "冠军", "亚军", "季军", "荣誉", "一等奖", "二等奖",
                  "三等奖", "优秀奖", "夺冠", "名列前茅", "奖项", "award", "prize", "champion",
                  "honour", "honor", "medal", "winner", "laurel"),
    ),
    Vibe(
        key="tech", label_cn="科技竞赛", label_en="Technology & innovation", motif="circuit",
        background="#070F22", primary="#10224A", accent="#35D6E8", secondary="#7B61FF", ink="#ECF6FF",
        mood_cn="创新、智慧、未来", mood_en="Innovation, intelligence, what's next",
        scene_en="an abstract circuit of glowing traces, hexagonal nodes and data lines over a grid",
        keywords=("智能", "智慧", "创新", "科技", "编程", "代码", "算法", "人工智能", "机器人", "数据",
                  "数字化", "建模", "创业", "apec", "code", "tech", "innovation", "hackathon",
                  "robot", "algorithm", "programming", "digital", "startup", "ai"),
    ),
    Vibe(
        key="winter", label_cn="冬日暖意", label_en="Winter", motif="snow",
        background="#0F2338", primary="#1B3870", accent="#8FD3F4", secondary="#D8E9F5", ink="#F5FAFF",
        mood_cn="清冽、温暖、相聚", mood_en="Crisp air, warmth indoors",
        scene_en="delicate six-armed snowflakes and frost crystals drifting through a soft blue haze",
        keywords=("寒冬", "冬天", "冬日", "冰雪", "雪", "圣诞", "元旦", "新春", "春节", "winter",
                  "snow", "christmas", "new year", "spring festival"),
    ),
    Vibe(
        key="global", label_cn="国际交流", label_en="International dialogue", motif="globe",
        background="#062A5A", primary="#0B4EA2", accent="#7EC8E3", secondary="#C9A227", ink="#F2F8FF",
        mood_cn="对话、视野、连接", mood_en="Dialogue, outlook, connection",
        scene_en="a wireframe globe with meridians and orbiting rings above a stylised skyline",
        keywords=("模联", "模拟联合国", "联合国", "国际交流", "外交", "全球化", "国际视野", "三校",
                  "国际学子", "mun", "model united nations", "diplomacy", "united nations",
                  "global", "summit", "exchange"),
    ),
    Vibe(
        key="music", label_cn="音乐交流", label_en="Music & performance", motif="wave",
        background="#150C2E", primary="#2A1550", accent="#E8467C", secondary="#F2A65A", ink="#FDF1F6",
        mood_cn="共鸣、节奏、知音", mood_en="Resonance, rhythm, kindred voices",
        scene_en="a flowing sound waveform ribbon, a stylised guitar silhouette and warm stage lights",
        keywords=("音乐", "歌曲", "合唱", "乐器", "吉他", "钢琴", "乐队", "音乐会", "以乐会友", "歌唱",
                  "music", "song", "concert", "band", "guitar", "piano", "choir", "melody", "acoustic"),
    ),
    Vibe(
        key="carnival", label_cn="社团嘉年华", label_en="Fair & recruitment", motif="flags",
        background="#14213D", primary="#1B3870", accent="#FF6B35", secondary="#FFD166", ink="#FFFDF7",
        mood_cn="热闹、开放、相聚", mood_en="Bustle, openness, joining in",
        scene_en="festival bunting flags strung between poles, paper lanterns and market stalls",
        keywords=("游园会", "社团", "摊位", "招新", "纳新", "嘉年华", "市集", "集市", "展位", "招募",
                  "报名", "迎新", "carnival", "club fair", "booth", "recruit", "market"),
    ),
    Vibe(
        key="celebration", label_cn="庆典回顾", label_en="Celebration & recap", motif="confetti",
        background="#101B33", primary="#1B3870", accent="#F2C14E", secondary="#FF6B6B", ink="#FFF9EC",
        mood_cn="圆满、欢庆、回望", mood_en="Success, joy, looking back",
        scene_en="a joyful burst of confetti, paper ribbons and geometric shapes rising upward",
        keywords=("圆满", "落幕", "收官", "成功举办", "联欢", "晚会", "庆", "celebrate", "celebration",
                  "successfully", "closing", "anniversary"),
    ),
    Vibe(
        key="brand", label_cn="品牌简约", label_en="House minimal", motif="geometric",
        background="#F4F6FA", primary="#1B3870", accent="#E8B04B", secondary="#20314B", ink="#1B3870",
        mood_cn="简洁、克制、官方", mood_en="Clean, restrained, official",
        scene_en="clean geometric shapes, diagonal bands and a fine dot grid in brand navy and gold",
        default_background="light",
    ),
)

BY_KEY = {vibe.key: vibe for vibe in VIBES}
FALLBACK = BY_KEY["brand"]

# Doc type nudges the motif when the text itself says nothing decisive. Kept
# weak on purpose: the words in the article should win over the label.
DOC_TYPE_HINTS: dict[str, tuple[str, float]] = {
    # A 喜报 is by definition about winning something, and the surrounding text
    # often talks about the competition that produced it (MUN, a contest, an
    # award ceremony). The hint has to outrank that noise or the poster shows
    # the venue of the win instead of the win.
    "喜报": ("award", 2.4),
    "竞赛": ("tech", 0.6),
    "招募": ("carnival", 0.6),
    "预告": ("carnival", 0.35),
    "回顾": ("celebration", 0.5),
    "收官": ("celebration", 0.8),
    "活动": ("brand", 0.3),
}

ANNOUNCING_TYPES = {"预告", "招募", "竞赛"}
CELEBRATING_TYPES = {"回顾", "收官", "喜报"}


def _weight(keyword: str) -> float:
    """Longer keywords are more specific, so they count for more."""
    return max(1.0, min(2.2, len(keyword) / 3.0))


def _count(haystack: str, keyword: str) -> int:
    if keyword.isascii():
        # Word boundaries, or "ai" matches "chair" and "code" matches "barcode".
        # A trailing s is allowed because these keywords are usually written in
        # the plural in English titles: "Three Awards at Penghai MUN" must still
        # count as award, or the MUN article gets a globe instead of a trophy.
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}s?(?![a-z0-9])"
        return len(re.findall(pattern, haystack))
    return haystack.count(keyword)


def classify(*texts: str, doc_type: str = "") -> tuple[Vibe, dict]:
    """Pick a vibe for an event.

    Returns the vibe plus the evidence behind it, so a reviewer can see which
    words drove the choice instead of taking it on faith.
    """
    haystack = " ".join(t for t in texts if t).lower()
    scores: dict[str, float] = {vibe.key: 0.0 for vibe in VIBES}
    matched: dict[str, list[str]] = {vibe.key: [] for vibe in VIBES}

    for vibe in VIBES:
        for keyword in vibe.keywords:
            hits = _count(haystack, keyword.lower())
            if hits:
                # Presence decides; repeats only nudge, so a keyword-stuffed
                # paragraph cannot hijack the palette.
                scores[vibe.key] += _weight(keyword) * (1.0 + 0.15 * min(hits - 1, 4))
                matched[vibe.key].append(keyword)

    hint = DOC_TYPE_HINTS.get((doc_type or "").strip())
    hint_note = ""
    if hint:
        key, boost = hint
        scores[key] = scores.get(key, 0.0) + boost
        hint_note = f"doc_type {doc_type} -> {key} (+{boost})"

    best = max(VIBES, key=lambda v: scores[v.key])
    # A tie or an empty field means the text told us nothing: prefer the doc
    # type hint, then the house brand look.
    if scores[best.key] <= 0.0:
        best = BY_KEY[hint[0]] if hint else FALLBACK

    evidence = {
        "vibe": best.key,
        "score": round(scores[best.key], 2),
        "matched_keywords": matched[best.key][:8],
        "doc_type_hint": hint_note,
        "runner_up": _runner_up(scores, best.key),
        "tone": tone_for(doc_type),
    }
    return best, evidence


def _runner_up(scores: dict[str, float], winner: str) -> dict | None:
    others = sorted((v for k, v in scores.items() if k != winner and v > 0), reverse=True)
    if not others:
        return None
    second = max((k for k, v in scores.items() if k != winner), key=lambda k: scores[k])
    return {"vibe": second, "score": round(scores[second], 2)}


def tone_for(doc_type: str) -> str:
    """How much room the layout should leave, and how warm the light is."""
    doc_type = (doc_type or "").strip()
    if doc_type in ANNOUNCING_TYPES:
        return "anticipation"
    if doc_type in CELEBRATING_TYPES:
        return "celebration"
    return "neutral"


def build_prompt(vibe: Vibe, *, event_hint: str = "", tone: str = "neutral",
                 aspect: str = "wide banner") -> str:
    """English prompt for an external text-to-image backend.

    The event hint is included verbatim so the picture responds to the actual
    subject, but it is trimmed hard: image models start producing garbled glyphs
    when a prompt reads like a sentence.
    """
    lighting = {
        "anticipation": "cool dawn light, hopeful atmosphere",
        "celebration": "warm golden light, festive atmosphere",
        "neutral": "balanced studio light",
    }.get(tone, "balanced studio light")
    subject = vibe.scene_en
    if event_hint:
        subject = f"{subject}, inspired by: {event_hint}"
    return (
        f"{subject}. {STYLE_EN}. {lighting}, {vibe.mood_en} mood. "
        f"Colour palette: {vibe.background} background, {vibe.primary} primary, "
        f"{vibe.accent} accent, {vibe.secondary} secondary. {aspect} composition."
    )
