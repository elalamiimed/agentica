"""Generative artwork for HSIYC articles.

Two backends, one interface:

``local``
    Drawn here with numpy and Pillow from the vibe's palette and motif. Always
    available, deterministic for a given seed, no network, no third party.
``remote``
    A real text-to-image model over the public Pollinations endpoint, prompted
    from the same vibe. Optional and allowed to fail; the asset falls back to
    ``local`` and the manifest records what actually happened.

The artwork decorates an article. It never occupies a photo slot: generated
pictures are labelled as illustrations, and the club submits to a youth
committee that would rightly object to a drawing standing in for a photograph
of something that happened.

    from hsiyc_writer.art import make_art
    manifest = make_art(article, "output/<slug>/art", backend="auto")
"""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "ArtUnavailable", "Caption", "capabilities", "make_art", "vibe_for",
    "ASSET_KINDS", "REMOTE_KINDS",
]

ASSET_KINDS = ("banner", "cover", "poster", "social", "dividers")
# The online model handles these three well. A 6:1 divider band and a 2.35:1 cover
# strip come back as mush, so those are always drawn locally.
REMOTE_KINDS = ("banner", "poster", "social")
MANIFEST_NAME = "manifest.json"

_READY: bool | None = None
_REASON = ""


class ArtUnavailable(RuntimeError):
    """The local renderer cannot run (missing numpy or Pillow)."""


def _ensure() -> None:
    """Import the drawing stack lazily so the package stays importable without it."""
    global _READY, _REASON
    if _READY is True:
        return
    if _READY is False:
        raise ArtUnavailable(_REASON)
    try:
        import numpy  # noqa: F401
        from . import local, motifs, remote, vibe
        from .canvas import Palette
    except Exception as exc:  # pragma: no cover - depends on the host
        _READY = False
        _REASON = f"artwork needs numpy and Pillow ({type(exc).__name__}: {exc})"
        raise ArtUnavailable(_REASON) from exc
    globals().update({"local": local, "motifs": motifs, "remote": remote,
                      "vibe": vibe, "Palette": Palette, "np": numpy})
    _READY = True


def _stack():
    _ensure()
    return globals()["local"], globals()["vibe"], globals()["remote"], globals()["Palette"], globals()["np"]


def capabilities(*, probe_remote: bool = False) -> dict:
    """What this machine can actually do, for the status endpoint and the CLI."""
    info: dict = {"local": False, "reason": "", "fonts": False, "remote": {}}
    try:
        import numpy
        import PIL

        info["numpy"] = numpy.__version__
        info["pillow"] = PIL.__version__
    except Exception as exc:
        info["reason"] = f"{type(exc).__name__}: {exc}"
        return info
    try:
        _ensure()
        from . import text as textmod

        path = textmod.cjk_font_path()
        info["fonts"] = path is not None
        info["cjk_font"] = str(path) if path else ""
    except ArtUnavailable as exc:
        info["reason"] = str(exc)
        return info
    local, _vibe, remote, _Palette, _np = _stack()
    info["local"] = True
    info["kinds"] = list(ASSET_KINDS)
    info["motifs"] = sorted(local.motifs.MOTIFS)
    info["remote"] = remote.status(probe=probe_remote)
    return info


# --------------------------------------------------------------------------- caption
def _caption_from(article: dict, brief: dict | None) -> object:
    """Pull the printable facts about the event out of the article."""
    local, _vibe, _remote, _Palette, _np = _stack()
    title = article.get("title") or {}
    meta = article.get("meta") or {}
    closing = article.get("closing") or {}
    signoff = article.get("signoff") or {}
    brief = brief or {}

    def pick(*values: str) -> str:
        for value in values:
            if value:
                return str(value).strip()
        return ""

    date_cn = _format_date(pick(meta.get("event_date"), brief.get("event_date")),
                           pick(meta.get("event_end_date"), brief.get("event_end_date")))
    time_cn = _format_time(brief)
    date_line = ""
    if date_cn or time_cn:
        joined = " ".join(part for part in (date_cn, time_cn) if part)
        date_line = f"时间：{joined}"
    venue = pick(meta.get("venue"), brief.get("venue"))
    venue_line = ""
    if venue:
        venue_line = f"地点：{venue}"

    tagline_cn = pick(closing.get("tagline_cn"))
    subtitle_cn = pick(title.get("subtitle_cn"))
    # What the event actually contained. A poster that says what happened is worth
    # posting; one with a headline alone is not.
    raw_highlights = brief.get("highlights") or []
    if isinstance(raw_highlights, str):
        raw_highlights = [raw_highlights]
    highlights = tuple(
        str(item).strip() for item in raw_highlights
        if str(item).strip() and len(str(item).strip()) <= 26
    )[:4]
    return local.Caption(
        title_cn=pick(title.get("cn"), brief.get("title_cn")),
        title_en=pick(title.get("en"), brief.get("title_en")),
        subtitle_cn="" if _redundant(subtitle_cn, tagline_cn) else subtitle_cn,
        kicker_en=pick(title.get("kicker_en"), signoff.get("en")),
        club_cn=pick(signoff.get("cn"), "哈工大（深圳）国际青年俱乐部"),
        club_en=pick(signoff.get("en"), "HITSZ International Youth Club"),
        doc_type_cn=pick(meta.get("doc_type"), brief.get("doc_type")),
        date_line=date_line,
        venue_line=venue_line,
        tagline_cn=tagline_cn,
        highlights=highlights,
    )


_ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_CN_DATE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def _to_iso(value: str) -> str:
    """Normalise either date spelling to ``YYYY-MM-DD``.

    The article usually stores the Chinese form (``2026年12月5日``) while a fresh
    brief stores ISO; both have to reach the formatter, and the weekday lookup
    only understands ISO - which is how a poster ends up missing its （周六）.
    """
    value = (value or "").strip()
    for pattern in (_ISO_DATE, _CN_DATE):
        match = pattern.search(value)
        if match:
            year, month, day = (int(group) for group in match.groups())
            return f"{year:04d}-{month:02d}-{day:02d}"
    return value


def _format_date(start: str, end: str = "") -> str:
    """House date style: 2026年12月12日（周六），ranges as 2026年7月19日至21日."""
    if not start:
        return ""
    try:
        from ..form import chinese_weekday, format_date

        iso_start, iso_end = _to_iso(start), _to_iso(end)
        text = format_date({"date_start": iso_start, "date_end": iso_end if end else ""})
        if not text:
            return start
        # Only a single day carries the weekday, matching the approved articles.
        weekday = chinese_weekday(iso_start) if not end or end == start else ""
        return f"{text}{weekday}"
    except Exception:
        return start


def _format_time(brief: dict) -> str:
    """Times are optional; render them only if the operator supplied them."""
    try:
        from ..form import format_time

        return format_time({
            "time_start": brief.get("time_start") or brief.get("start_time") or "",
            "time_end": brief.get("time_end") or brief.get("end_time") or "",
        })
    except Exception:
        start = str(brief.get("time_start") or "").strip()
        end = str(brief.get("time_end") or "").strip()
        return f"{start}-{end}" if start and end else (start or end)


def _redundant(a: str, b: str, threshold: float = 0.55) -> bool:
    """True when two short lines reuse most of the same characters.

    Article subtitles and closing taglines are often near-twins; printing both on
    a poster looks like a mistake even though both are correct in the document.
    """
    first, second = set(a or ""), set(b or "")
    if len(first) < 4 or len(second) < 4:
        return False
    return len(first & second) / min(len(first), len(second)) >= threshold



# --------------------------------------------------------------------------- vibe
def _event_text(article: dict, brief: dict | None, extra: tuple[str, ...] = ()) -> list[str]:
    brief = brief or {}
    title = article.get("title") or {}
    lead = article.get("lead") or {}
    closing = article.get("closing") or {}
    meta = article.get("meta") or {}
    sections = article.get("sections") or []
    parts: list[str] = [
        str(title.get("cn") or ""), str(title.get("en") or ""),
        str(title.get("subtitle_cn") or ""), str(title.get("subtitle_en") or ""),
        str(lead.get("cn") or "")[:600], str(lead.get("en") or "")[:600],
        str(closing.get("tagline_cn") or ""),
        str(meta.get("venue") or ""), str(meta.get("doc_type") or ""),
    ]
    for section in sections:
        parts.append(str(section.get("heading_cn") or ""))
        parts.append(str(section.get("heading_en") or ""))
    for key in ("highlights", "programme", "winners", "quotes", "photo_notes", "participants_count"):
        value = brief.get(key)
        if isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    parts.extend(str(item) for item in extra)
    return [part for part in parts if part]


def vibe_for(article: dict, brief: dict | None = None, extra: tuple[str, ...] = ()) -> tuple[object, dict]:
    """Which visual identity an article gets, and the evidence for it."""
    _local, vibe, _remote, _Palette, _np = _stack()
    meta = article.get("meta") or {}
    doc_type = str(meta.get("doc_type") or (brief or {}).get("doc_type") or "")
    return vibe.classify(*_event_text(article, brief, extra), doc_type=doc_type)


def _event_hint(article: dict, brief: dict | None) -> str:
    """A few words of real subject matter for the image prompt.

    Kept short on purpose: image models start rendering garbled lettering when a
    prompt reads like prose, and a long Chinese sentence is the fastest way to
    get nonsense glyphs baked into the picture.
    """
    title = article.get("title") or {}
    text = str(title.get("en") or "").strip() or str(title.get("cn") or "").strip()
    text = re.sub(r"^[^|｜]*[|｜]\s*", "", text)
    text = re.sub(r"^(Recap|Preview|Recruitment|Closing|Awards|Competition)\s*[:\-–]\s*", "", text, flags=re.I)
    hint = text[:90].strip(" -–:：")
    meta = article.get("meta") or {}
    doc_type = str(meta.get("doc_type") or "").strip()
    if doc_type == "喜报":
        hint = f"an award announcement, {hint}" if hint else "an award announcement"
    return hint


# --------------------------------------------------------------------------- main
def _seed_for(article: dict, explicit: int | None) -> int:
    if explicit is not None:
        return int(explicit) & 0x7FFFFFFF
    meta = article.get("meta") or {}
    basis = f"{meta.get('slug','')}|{meta.get('event_date','')}|{meta.get('doc_type','')}"
    import hashlib

    return int(hashlib.sha1(basis.encode("utf-8")).hexdigest()[:8], 16) & 0x7FFFFFFF


def make_art(article: dict, out_dir: str | Path, *, brief: dict | None = None,
             backend: str = "auto", kinds: tuple[str, ...] | None = None,
             seed: int | None = None, light: bool = False, credit: bool = True,
             extra_keywords: tuple[str, ...] = (), notes: list[str] | None = None) -> dict:
    """Render the artwork for one article and write ``manifest.json``.

    ``backend``: ``local`` (never touches the network), ``remote`` (must use the
    online model, raises if it cannot), or ``auto`` (online, quietly falls back).
    """
    local, vibe_mod, remote, Palette, np = _stack()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    notes = notes if notes is not None else []

    backend = (backend or "auto").strip().lower()
    if backend not in {"auto", "local", "remote"}:
        raise ArtUnavailable(f"unknown art backend {backend!r}; use auto, local or remote")
    if backend == "remote" and remote.offline():
        raise remote.RemoteArtError("backend 'remote' requested but HSIYC_ART_OFFLINE is set")

    wanted = tuple(kinds) if kinds else ASSET_KINDS
    unknown = [kind for kind in wanted if kind not in ASSET_KINDS]
    if unknown:
        raise ArtUnavailable(f"unknown asset kind(s): {', '.join(unknown)}")

    v, evidence = vibe_mod.classify(*_event_text(article, brief, extra_keywords),
                                    doc_type=str((article.get("meta") or {}).get("doc_type")
                                                 or (brief or {}).get("doc_type") or ""))
    pal = Palette.from_hex(v.palette)
    caption = _caption_from(article, brief)
    base_seed = _seed_for(article, seed)

    def asset_seed(kind: str, section: int = 0) -> int:
        return int(hashlib.sha256(f"{base_seed}|{kind}|{section}".encode()).hexdigest()[:8], 16)
    tone = evidence.get("tone", "neutral")
    prompt = vibe_mod.build_prompt(v, event_hint=_event_hint(article, brief), tone=tone)

    sections = article.get("sections") or []
    assets: list[dict] = []
    remote_failed = ""

    def _remote_background(kind: str):
        """Return a generated picture, or None if the online route is unavailable."""
        nonlocal remote_failed
        if backend == "local" or kind not in REMOTE_KINDS:
            return None
        if remote_failed:
            notes.append(f"{kind}: online generation skipped after provider failure; drawn locally instead")
            return None
        width, height = local.KIND_SIZES[kind]
        composition = {
            "banner": "wide landscape, subject on the right with open space on the left",
            "poster": "portrait, complete subject in the upper half, quiet lower half for a separate text panel",
            "social": "square, complete subject in the upper half, quiet lower half for a separate text panel",
        }[kind]
        asset_prompt = vibe_mod.build_prompt(v, event_hint=_event_hint(article, brief),
                                             tone=tone, aspect=composition)
        try:
            result = remote.generate(asset_prompt, width, height, seed=asset_seed(kind))
        except remote.RemoteArtError as exc:
            remote_failed = str(exc)
            if backend == "remote":
                raise
            notes.append(f"{kind}: online image generation unavailable ({exc}); drawn locally instead")
            return None
        notes.append(f"{kind}: generated by {result['model']} (seed {result['seed']}"
                     f"{', cached' if result['cached'] else ''})")
        return result

    def _write(kind: str, image, caption_cn: str, caption_en: str, section: int | None = None,
               origin: dict | None = None) -> None:
        filename = f"{kind}-{section:02d}.png" if kind == "divider" and section is not None else f"{kind}.png"
        path = out / filename
        image.save(path, format="PNG", optimize=True)
        # Dividers are always drawn locally, but every asset carries provenance
        # so a reader never has to know which kinds can come from elsewhere.
        origin = origin or {"backend": "local", "motif": v.motif, "renderer": "hsiyc_writer.art.local"}
        entry = {
            "kind": kind,
            "file": filename,
            "width": image.width,
            "height": image.height,
            "caption_cn": caption_cn,
            "caption_en": caption_en,
            "section": section,
            "backend": origin.get("backend", "local"),
            "seed": asset_seed(kind, section or 0),
            "light": light,
            "provenance": origin,
        }
        assets.append(entry)

    def _origin(backend_name: str, result: dict | None) -> dict:
        if result is None:
            return {"backend": "local", "motif": v.motif, "renderer": "hsiyc_writer.art.local"}
        return {
            "backend": result.get("backend", "remote:pollinations"),
            "model": result["model"],
            "seed": result["seed"],
            "prompt": result["prompt"],
            "url": result["url"],
            "cached": result["cached"],
            "post_process": "harmonise(local palette)",
        }

    for kind in wanted:
        if kind == "dividers":
            for index, _section in enumerate(sections or [], start=1):
                rng = np.random.default_rng(asset_seed("divider", index))
                image = local.render("divider", v, pal, rng, caption, light=light, credit=credit)
                _write("divider", image, f"{v.label_cn}分隔图 {index:02d}", f"{v.label_en} divider {index:02d}",
                       section=index, origin=None)
            continue
        rng = np.random.default_rng(asset_seed(kind))
        result = _remote_background(kind)
        # The free service stamps its own logo into the corner even when asked
        # not to; club material must not carry a third-party brand.
        background = None
        if result:
            picture = result["image"]
            if result.get("backend", "remote:pollinations") == "remote:pollinations":
                picture = local.strip_vendor_marks(picture)
            background = local.harmonise(picture, pal, rng)
        image = local.render(kind, v, pal, rng, caption, light=light, credit=credit, background=background)
        captions = {
            "banner": (f"{v.label_cn}主题横幅", f"{v.label_en} banner"),
            "cover": (f"{v.label_cn}公众号封面", f"{v.label_en} WeChat cover"),
            "poster": (f"{v.label_cn}活动海报", f"{v.label_en} poster"),
            "social": (f"{v.label_cn}社交卡片", f"{v.label_en} social card"),
        }[kind]
        _write(kind, image, captions[0], captions[1], origin=_origin(kind, result))

    # A partial re-render ("just the banner, thanks") must not throw away the
    # poster the deck and the preview already point at, so the new assets are
    # merged over whatever was there before.
    previous = load_manifest(out) or {}
    if kinds and previous.get("assets"):
        wanted_kinds = {"divider" if kind == "dividers" else kind for kind in wanted}
        assets = [a for a in previous["assets"] if a.get("kind") not in wanted_kinds] + assets
        if previous.get("seed") == _seed_for(article, seed):
            notes = [*previous.get("notes", []), *notes]

    backends = {a.get("backend", "local") for a in assets}
    summary_backend = next(iter(backends)) if len(backends) == 1 else ("mixed" if backends else "local")
    manifest = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backend": summary_backend,
        "requested_backend": backend,
        "seed": _seed_for(article, seed),
        "vibe": {**v.as_dict(), "tone": tone},
        "vibe_evidence": evidence,
        "prompt": prompt,
        "source": {
            "slug": (article.get("meta") or {}).get("slug", ""),
            "title_cn": caption.title_cn,
            "title_en": caption.title_en,
            "event_date": (article.get("meta") or {}).get("event_date", ""),
            "venue": (article.get("meta") or {}).get("venue", ""),
            "doc_type": caption.doc_type_cn,
        },
        "assets": assets,
        "notes": notes,
        "disclaimer_cn": "本页插画由程序生成，不是活动现场照片。",
        "disclaimer_en": "Artwork on this page is programmatically generated and is not a photograph of the event.",
    }
    (out / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_manifest(out_dir: str | Path) -> dict | None:
    """Read a manifest if one exists (used by the Office exporters and the UI)."""
    path = Path(out_dir) / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
