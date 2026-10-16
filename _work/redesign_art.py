from pathlib import Path
p=Path('hsiyc_writer/art/local.py')
s=p.read_text(encoding='utf-8')
a=s.index('def poster('); b=s.index('\ndef _corner_rules', a)
s=s[:a]+'''def _editorial(kind: str, vibe: Vibe, pal: Palette, rng, caption: Caption, *,
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

    # The image occupies a deliberate frame instead of a vague empty upper half.
    art_top, art_bottom = round(height * .325), round(height * .765)
    art_h = art_bottom - art_top
    if background is not None:
        picture = _fit_background(background, inner, art_h)
    else:
        picture = _background(inner, art_h, pal, rng, light=False, tone="neutral")
        graphic = canvas.Painter(inner, art_h)
        shapes = graphic.begin()
        radius = min(inner * .39, art_h * .57)
        shapes.circle(inner * .5, art_h * .5, radius, fill=canvas.rgba(pal.accent, 32),
                      outline=canvas.rgba(pal.accent, 105), width=1.5)
        shapes.circle(inner * .5, art_h * .5, radius * .82, outline=canvas.rgba(pal.ink, 50), width=1)
        motifs.draw(vibe.motif, graphic, pal, rng, (inner * .06, art_h * .07, inner * .88, art_h * .86))
        picture = canvas.alpha_composite(picture, graphic.composite())
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

''' + s[b:]
p.write_text(s,encoding='utf-8')
