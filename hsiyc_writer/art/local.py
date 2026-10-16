"""Compose the assets: banner, poster, social card and section dividers.

Layout rules that matter here:

* The **banner** and **dividers** carry no article text. They are used as slide
  backgrounds and section rules, where baked-in text fights the editable text on
  top of it. Text lives on the poster and the social card, which are standalone
  graphics meant to be posted as-is.
* Any panel with text gets an opaque scrim behind it, so contrast does not
  depend on how the generative art happened to land.
* Every asset carries a small provenance line saying it is an AI illustration
  and not an event photograph. The club submits these to a youth committee;
  passing generated art off as a photo of something that happened would be a
  worse failure than a rejected article.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from . import canvas, motifs, text as textmod
from .canvas import Palette
from .vibe import Vibe

KIND_SIZES: dict[str, tuple[int, int]] = {
    "banner": (1600, 900),
    "poster": (1240, 1754),
    "social": (1080, 1080),
    # WeChat crops an article cover to roughly 2.35:1. Supplying that ratio natively
    # stops the app slicing the club's headline off the banner.
    "cover": (900, 383),
    "divider": (1600, 260),
}

CREDIT_CN = "AI 生成插画（非活动照片）"
CREDIT_EN = "AI-generated artwork (not an event photo)"


@dataclass
class Caption:
    """Everything the poster/social card may print about the event."""

    title_cn: str = ""
    title_en: str = ""
    subtitle_cn: str = ""
    kicker_en: str = "HITSZ International Youth Club"
    club_cn: str = "哈工大（深圳）国际青年俱乐部"
    club_en: str = "HITSZ International Youth Club"
    doc_type_cn: str = ""
    date_line: str = ""
    venue_line: str = ""
    tagline_cn: str = ""
    highlights: tuple[str, ...] = ()


# --------------------------------------------------------------------------- picture engine
def _dust(layer: canvas.Layer, pal: Palette, rng, width: float, height: float,
          *, count: int | None = None) -> None:
    """Foreground specks and light beams.

    Depth in a flat illustration comes from layering, not from detail: a few
    particles in front of the subject read as air between the viewer and the
    scene, which is what stops the picture looking like a sticker.
    """
    total = count if count is not None else max(28, int(width * height / 14000))
    for _ in range(total):
        x, y = rng.random() * width, rng.random() * height
        layer.circle(x, y, rng.uniform(0.7, 3.2), fill=canvas.rgba(pal.ink, int(rng.integers(24, 105))))
    for _ in range(2):
        cy = rng.uniform(0.15, 0.85) * height
        layer.polygon_rotated(width * 0.5, cy, width * 1.3, height * rng.uniform(0.015, 0.035),
                              rng.uniform(-14, 14), fill=canvas.rgba(pal.accent, int(rng.integers(9, 17))))
    # A large dim disc bleeding off an edge balances a motif parked on the other
    # side; without it a banner with a clear text half looks half-finished.
    bleed = rng.choice([-1, 1])
    layer.circle(width * (0.5 + bleed * 0.52), height * rng.uniform(0.72, 0.95),
                 min(width, height) * rng.uniform(0.30, 0.42), fill=canvas.rgba(pal.accent, 20))


def _fit_subject(subject: Image.Image, width: int, height: int, *, threshold: int = 48,
                 margin: float = 0.035) -> Image.Image:
    """Scale a drawn motif so its ink fills the frame without touching the edges.

    Motifs use their box very differently - lanterns hang from the top, confetti
    fills everything, a globe is a circle in the middle - so composing by box
    alone either crops the tall ones or leaves the small ones floating in dead
    space. Measuring what was actually drawn fixes both at once, and it means a
    new motif cannot be added badly.
    """
    mask = subject.convert("RGBA").split()[-1].point(lambda value: 255 if value > threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return subject
    crop = subject.crop(bbox)
    avail_w, avail_h = width * (1 - margin * 2), height * (1 - margin * 2)
    scale = min(avail_w / crop.width, avail_h / crop.height)
    scaled = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
                         Image.LANCZOS)
    placed = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    placed.paste(scaled, ((width - scaled.width) // 2, (height - scaled.height) // 2), scaled)
    return placed


def _motif_panel(width: int, height: int, vibe: Vibe, pal: Palette, rng, *,
                 box: tuple[float, float, float, float] | None = None,
                 frame_radius: float | None = None, dust: bool = True,
                 tone: str = "neutral", light: bool = False, fit: bool = True) -> Image.Image:
    """Atmosphere, a grounded motif and foreground dust - the shared picture engine.

    Every asset family builds its illustration through here, so a change to the
    look lands everywhere at once instead of in one layout.

    ``fit`` measures the drawing and scales it to fill its box. That is right for
    a framed poster panel, where the alternative is dead space. It is wrong for a
    wide banner: the fit bbox swallows decorative scatter like confetti and rays,
    which shrinks the actual subject, so those draw straight into a generous box
    instead and are allowed to bleed.
    """
    base = _background(width, height, pal, rng, light=light, tone=tone)
    p = canvas.Painter(width, height)

    if frame_radius:
        layer = p.begin()
        cx, cy = width * 0.5, height * 0.5
        layer.circle(cx, cy, frame_radius, fill=canvas.rgba(pal.accent, 24),
                     outline=canvas.rgba(pal.accent, 92), width=1.5)
        layer.circle(cx, cy, frame_radius * 0.82, outline=canvas.rgba(pal.ink, 42), width=1)

    bx, by, bw, bh = box or (width * 0.06, height * 0.07, width * 0.88, height * 0.86)
    subject = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if fit:
        graphic = canvas.Painter(int(bw), int(bh))
        motifs.draw(vibe.motif, graphic, pal, rng, (0.0, 0.0, float(bw), float(bh)))
        drawn = _fit_subject(graphic.composite(), int(bw), int(bh))
        subject.paste(drawn, (int(bx), int(by)), drawn)
    else:
        graphic = canvas.Painter(width, height)
        motifs.draw(vibe.motif, graphic, pal, rng, (bx, by, bw, bh))
        subject = graphic.composite()

    # The shadow is offset, not centred. Most motifs are translucent, so a blur
    # sitting directly behind them shows through and muddies the fill - the
    # lanterns turned into hollow rings that way.
    depth = max(4.0, min(width, height) * 0.012)
    shadow = canvas.shadow_of(subject, min(width, height) * 0.030, 0.45)
    dropped = Image.new("RGBA", subject.size, (0, 0, 0, 0))
    dropped.paste(shadow, (0, int(round(depth))), shadow)
    base = canvas.alpha_composite(base, dropped, subject)

    if dust:
        layer = p.begin()
        _dust(layer, pal, rng, width, height)
    return canvas.finish_image(canvas.alpha_composite(base, p.composite()), grain=1.8,
                               seed=int(rng.integers(1 << 30)))


# --------------------------------------------------------------------------- helpers
def clean_title(value: str) -> str:
    """Strip the house prefix so a poster headline reads like a headline.

    Article titles look like ``哈工大（深圳）国际青年俱乐部 | 回顾：...``; the
    club name and the doc-type word are useful in a document and noise on a
    poster, where both are already present elsewhere.
    """
    text = (value or "").strip()
    for separator in ("|", "｜"):
        if separator in text:
            text = text.split(separator, 1)[1].strip()
    for prefix in ("活动回顾：", "活动预告：", "回顾：", "预告：", "招募：", "喜报：", "收官：", "竞赛：", "活动："):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text


def _background(width: int, height: int, pal: Palette, rng, *, light: bool, tone: str) -> Image.Image:
    """Gradient, atmospheric clouds, a colour wash and a vignette."""
    if light:
        stops = [(0.0, canvas.shade(pal.background, 0.98)), (0.55, (255, 255, 255)),
                 (1.0, canvas.shade(pal.primary, 1.86))]
        angle = 118
    else:
        stops = [(0.0, canvas.shade(pal.background, 0.55)), (0.48, pal.background),
                 (1.0, canvas.shade(pal.primary, 0.62))]
        angle = 108
    array = canvas.gradient(width, height, stops, angle)

    clouds = canvas.fbm(width, height, scale=max(48, min(width, height) // 6), octaves=4, seed=int(rng.integers(1 << 30)))
    strength = 12.0 if light else 26.0
    array += (clouds[:, :, None] - 0.5) * strength

    # A warm or cool wash, depending on the doc type's tone.
    wash = {"anticipation": pal.accent, "celebration": pal.accent, "neutral": pal.primary}.get(tone, pal.primary)
    array += canvas.glow(width, height, wash, centre=(0.30, 0.24), radius=1.35, strength=0.22 if light else 0.30)
    array += canvas.glow(width, height, pal.secondary, centre=(0.86, 0.82), radius=1.1,
                         strength=0.10 if light else 0.16)
    array *= canvas.vignette(width, height, 0.10 if light else 0.34)[:, :, None]
    return canvas.to_image(array)


def _fit_background(image: Image.Image, width: int, height: int) -> Image.Image:
    """Centre-crop a supplied picture to the asset's aspect ratio."""
    source = image.convert("RGB")
    target_ratio = width / height
    current = source.width / max(1, source.height)
    if current > target_ratio:
        new_w = max(1, int(round(source.height * target_ratio)))
        left = (source.width - new_w) // 2
        source = source.crop((left, 0, left + new_w, source.height))
    elif current < target_ratio:
        new_h = max(1, int(round(source.width / target_ratio)))
        top = (source.height - new_h) // 2
        source = source.crop((0, top, source.width, top + new_h))
    return source.resize((width, height), Image.LANCZOS)


def strip_vendor_marks(image: Image.Image, fraction: float = 0.075) -> Image.Image:
    """Crop the bottom strip, where the free image service stamps its logo.

    ``nologo=true`` is requested but not always honoured, and club material must
    not carry a third-party brand. Provenance is not lost: the manifest records
    the service, model, prompt and URL for every generated asset.
    """
    if fraction <= 0:
        return image
    cut = int(round(image.height * fraction))
    if cut <= 0 or image.height - cut < 64:
        return image
    return image.crop((0, 0, image.width, image.height - cut))


def harmonise(image: Image.Image, pal: Palette, rng, *, strength: float = 0.16) -> Image.Image:
    """Tint an external picture toward the vibe's palette.

    A generated image arrives with its own colours; blending a palette gradient
    over it is what makes an AI banner and a drawn poster look like they belong
    to the same club rather than to two different artists. The strength is kept
    low and the contrast is restored afterwards - tinting alone flattens a
    generated picture into grey mush.
    """
    array = canvas.to_array(image)
    width, height = image.size
    wash = canvas.gradient(width, height,
                           [(0.0, canvas.shade(pal.primary, 1.15)), (0.50, pal.background),
                            (1.0, pal.accent)], 120)
    array = array * (1.0 - strength) + wash * strength
    array = 128.0 + (array - 128.0) * 1.08  # give back the contrast the tint ate
    array += canvas.glow(width, height, pal.accent, centre=(0.78, 0.20), radius=1.15, strength=0.08)
    array *= canvas.vignette(width, height, 0.20)[:, :, None]
    return canvas.finish_image(canvas.to_image(array), grain=2.2, seed=int(rng.integers(1 << 30)))


def _credit_line(p: canvas.Painter, pal: Palette, x: float, y: float, width: float, *,
                 light: bool, align: str = "right") -> None:
    layer = p.begin()
    size = 12.5
    label_cn = f"{CREDIT_CN} · {CREDIT_EN}"
    font = textmod.load(int(size), bold=False)
    if font is None:
        return
    label = textmod.ellipsize(label_cn, font, width)
    length = font.getlength(label)
    start = x + width - length if align == "right" else x
    colour = canvas.shade(pal.primary, 1.35) if light else canvas.mix(pal.ink, pal.background, 0.35)
    layer.text(start, y, label, size, canvas.rgba(colour, 190), anchor="la", bold=False)


# --------------------------------------------------------------------------- assets
def _wide(width: int, height: int, vibe: Vibe, pal: Palette, rng, *,
          background: Image.Image | None, light: bool = False) -> Image.Image:
    """A wide strip: motif to the right, clear space on the left for overlaid text."""
    if background is not None:
        base = _fit_background(background, width, height)
        p = canvas.Painter(width, height)
        layer = p.begin()
        _dust(layer, pal, rng, width, height)
        return canvas.finish_image(canvas.alpha_composite(base, p.composite()), grain=1.6,
                                   seed=int(rng.integers(1 << 30)))
    # Size the motif from the SHORT edge, so the same rule works for a 16:9 banner
    # and a 2.35:1 cover: derived from height alone, the cover's motif overflowed
    # the strip and got sliced top and bottom.
    span = min(width, height)
    box = (width - span * 0.98, -span * 0.05, span * 1.02, height + span * 0.10)
    return _motif_panel(width, height, vibe, pal, rng, box=box, light=light, fit=False)


def _stamp_credit(image: Image.Image, pal: Palette, *, credit: bool, light: bool) -> Image.Image:
    if not credit:
        return image
    p = canvas.Painter(image.width, image.height)
    # Wide enough for the whole disclaimer: at 45% of a 900px cover it was being
    # ellipsized to "...AI-generated artwork (not an event pho", which is exactly
    # the half of the label that matters.
    _credit_line(p, pal, image.width * 0.045, image.height * 0.90,
                 image.width * 0.90, light=light, align="left")
    return canvas.alpha_composite(image, p.composite())


def banner(vibe: Vibe, pal: Palette, rng, *, light: bool = False, credit: bool = True,
           caption: Caption | None = None, background: Image.Image | None = None) -> Image.Image:
    """Wide, text-free artwork for slide backgrounds and article headers."""
    width, height = KIND_SIZES["banner"]
    return _stamp_credit(_wide(width, height, vibe, pal, rng, background=background, light=light),
                         pal, credit=credit, light=light)


def cover(vibe: Vibe, pal: Palette, rng, *, light: bool = False, credit: bool = True,
          caption: Caption | None = None, background: Image.Image | None = None) -> Image.Image:
    """WeChat article cover, at the ratio the app crops to anyway."""
    width, height = KIND_SIZES["cover"]
    return _stamp_credit(_wide(width, height, vibe, pal, rng, background=background, light=light),
                         pal, credit=credit, light=light)


def divider(vibe: Vibe, pal: Palette, rng, *, light: bool = False,
            background: Image.Image | None = None) -> Image.Image:
    """A thin band: soft field on the left, motif on the right, one accent rule."""
    width, height = KIND_SIZES["divider"]
    base = (_fit_background(background, width, height) if background is not None
            else _background(width, height, pal, rng, light=light, tone="neutral"))
    p = canvas.Painter(width, height)
    if background is None:
        # A complete motif seated inside the band, not a fragment cropped by the
        # top edge: a 260px strip only has room for the whole shape or none of it,
        # and half a lantern reads as a mistake.
        motifs.draw(vibe.motif, p, pal, rng, (width * 0.735, height * 0.05, width * 0.225, height * 0.90))
    layer = p.begin()
    layer.rect((0, height - 6, width, height), fill=canvas.rgba(pal.accent, 255))
    layer.rect((0, height - 16, width * 0.22, height - 6), fill=canvas.rgba(pal.accent, 120))
    # No grain here: on a flat 1600x260 band it is invisible, and it turns a
    # 40 KB PNG into a 400 KB one because noise does not compress.
    return canvas.alpha_composite(base, p.composite())


def _editorial(kind: str, vibe: Vibe, pal: Palette, rng, caption: Caption, *,
               light: bool, credit: bool, background: Image.Image | None) -> Image.Image:
    """Type-led event artwork with a framed visual and a separate information rail."""
    width, height = KIND_SIZES[kind]
    square = kind == "social"
    margin = round(width * 0.065)
    inner = width - 2 * margin
    dark = not light and vibe.key in {"photography", "tech", "music", "global"}
    paper = canvas.shade(pal.background, 0.72) if dark else (247, 244, 235)
    ink = (247, 244, 235) if dark else (24, 29, 37)
    muted = canvas.mix(ink, paper, 0.66)
    accent = pal.accent if dark else canvas.shade(pal.primary, 0.70)
    base = Image.new("RGB", (width, height), paper)
    p = canvas.Painter(width, height)
    layer = p.begin()
    layer.rect((margin, height * .043, margin + 9, height * .077), fill=canvas.rgba(accent))
    layer.text(margin + 24, height * .042, "HSIYC", 25 if square else 28, canvas.rgba(ink))
    layer.text(margin + 24, height * .042 + 34, "INTERNATIONAL YOUTH CLUB", 10 if square else 12,
               canvas.rgba(muted), bold=False)
    label = caption.doc_type_cn or vibe.label_cn
    font = textmod.load(18)
    label = textmod.ellipsize(label, font, inner * .35)
    layer.text(width - margin, height * .049, label, 18, canvas.rgba(accent), anchor="ra")
    layer.line([(margin, height * .091), (width - margin, height * .091)], fill=canvas.rgba(ink, 95), width=1)

    title_top = height * .111
    font, rows, size = textmod.fit_size(clean_title(caption.title_cn), inner, 2,
        start=76 if square else 100, minimum=30 if square else 40,
        max_height=height * .135, line_height=1.13)
    layer.lines(margin - 3, title_top, rows, size, canvas.rgba(ink), line_height=1.13)
    cursor = title_top + len(rows) * size * 1.13 + height * .013
    if caption.title_en:
        _, rows, size = textmod.fit_size(clean_title(caption.title_en), inner * .94, 2,
            start=23 if square else 29, minimum=16, max_height=height * .052, bold=False)
        layer.lines(margin, cursor, rows, size, canvas.rgba(muted), bold=False)
        cursor += len(rows) * size * 1.34

    # The frame starts where the headline ends. A fixed offset left a band of dead
    # paper under a one-line title, which is the most common case.
    art_top = round(min(max(cursor + height * .035, height * .24), height * .40))
    art_bottom = round(height * .765)
    art_h = max(80, art_bottom - art_top)
    if background is not None:
        picture = _fit_background(background, inner, art_h)
    else:
        picture = _motif_panel(inner, art_h, vibe, pal, rng,
                               frame_radius=min(inner * .39, art_h * .57), tone="neutral")
    base.paste(picture.convert("RGB"), (margin, art_top))
    # A small editorial tab anchors the picture to the typography.
    tab_w = min(inner * .48, 345)
    layer.rect((margin, art_top, margin + tab_w, art_top + 36), fill=canvas.rgba(paper))
    tab = textmod.ellipsize((caption.kicker_en or vibe.label_en).upper(), textmod.load(12), tab_w - 20)
    layer.text(margin + 10, art_top + 8, tab, 12, canvas.rgba(ink))

    footer_top = height * .795
    label_size = 11 if square else 13
    body_size = 21 if square else 26
    facts = [("WHEN / 时间", caption.date_line.removeprefix("时间：")),
             ("WHERE / 地点", caption.venue_line.removeprefix("地点："))]
    col_w = (inner - 42) / 2
    for index, (label, value) in enumerate(facts):
        if not value:
            continue
        x = margin + index * (col_w + 42)
        layer.text(x, footer_top, label, label_size, canvas.rgba(accent))
        _, rows, size = textmod.fit_size(value, col_w, 2, start=body_size, minimum=15,
                                       max_height=height * .062, bold=False)
        layer.lines(x, footer_top + label_size + 13, rows, size, canvas.rgba(ink), bold=False)

    # Event highlights, when the operator gave any: a poster that lists what the
    # event actually contained is worth posting, one with a headline alone is not.
    if caption.highlights:
        items = [h.strip() for h in caption.highlights if str(h).strip()][:4]
        if items:
            text = "  ·  ".join(items)
            _, rows, size = textmod.fit_size(text, inner, 2, start=19 if square else 22,
                                            minimum=13, max_height=height * .030, bold=False)
            layer.lines(margin, footer_top + label_size + 13 + body_size * 1.7, rows, size,
                        canvas.rgba(canvas.mix(ink, paper, 0.30)), bold=False)

    layer.line([(margin, height * .90), (width - margin, height * .90)], fill=canvas.rgba(ink, 90), width=1)
    footer_text = caption.tagline_cn or caption.subtitle_cn or caption.club_cn
    layer.text(margin, height * .917, textmod.ellipsize(footer_text, textmod.load(18), inner),
               18, canvas.rgba(ink))
    if credit:
        label = f"{CREDIT_CN} · {CREDIT_EN}"
        label = textmod.ellipsize(label, textmod.load(12, bold=False), inner)
        layer.text(margin, height * .967, label, 12, canvas.rgba(muted), bold=False)
    return canvas.finish_image(canvas.alpha_composite(base, p.composite()), grain=.65,
                               seed=int(rng.integers(1 << 30)))


def poster(vibe: Vibe, pal: Palette, rng, caption: Caption, *, light: bool = False,
           credit: bool = True, background: Image.Image | None = None) -> Image.Image:
    return _editorial("poster", vibe, pal, rng, caption, light=light, credit=credit, background=background)


def social(vibe: Vibe, pal: Palette, rng, caption: Caption, *, light: bool = False,
           credit: bool = True, background: Image.Image | None = None) -> Image.Image:
    return _editorial("social", vibe, pal, rng, caption, light=light, credit=credit, background=background)


# --------------------------------------------------------------------------- dispatch
def render(kind: str, vibe: Vibe, pal: Palette, rng, caption: Caption, *, light: bool = False,
           credit: bool = True, background: Image.Image | None = None) -> Image.Image:
    if kind == "banner":
        return banner(vibe, pal, rng, light=light, credit=credit, caption=caption, background=background)
    if kind == "cover":
        return cover(vibe, pal, rng, light=light, credit=credit, caption=caption, background=background)
    if kind == "poster":
        return poster(vibe, pal, rng, caption, light=light, credit=credit, background=background)
    if kind == "social":
        return social(vibe, pal, rng, caption, light=light, credit=credit, background=background)
    if kind == "divider":
        return divider(vibe, pal, rng, light=light, background=background)
    raise ValueError(f"unknown asset kind: {kind}")
