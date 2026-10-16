"""Command-line entry point.

    python -m hsiyc_writer web                      start the browser UI
    python -m hsiyc_writer generate -b brief.md     write one article
    python -m hsiyc_writer generate -b brief.md -p photos/ --doc-type 回顾 -o output
    python -m hsiyc_writer check article.json       run the pre-submission check only
    python -m hsiyc_writer corpus                   show the approved-article corpus
    python -m hsiyc_writer key                      show the configured API key (masked)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import OUTPUT_DIR, PACKAGE_DIR, Settings, ensure_dirs, mask
from .pipeline import ArticleAgent, collect_photos, load_brief_file
from .retrieval import Corpus
from .validate import validate


def _force_utf8_console() -> None:
    """Windows consoles default to a legacy code page; Chinese output needs UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError, ValueError):
            pass


def _settings(args) -> Settings:
    settings = Settings.load(require_key=not getattr(args, "offline", False))
    if getattr(args, "model", None):
        settings.text_model = args.model
    if getattr(args, "no_vision", False):
        settings.vision_enabled = False
    return settings


# --------------------------------------------------------------------------- commands
def cmd_generate(args) -> int:
    settings = _settings(args)
    brief_text = load_brief_file(args.brief)
    photos = collect_photos(args.photo or [])

    print(f"HSIYC article writer")
    print(f"  key        : {mask(settings.api_key)}")
    print(f"  text model : {settings.text_model}")
    print(f"  vision     : {settings.vision_model if settings.vision_enabled else 'off'}")
    print(f"  brief      : {args.brief} ({len(brief_text)} chars)")
    print(f"  photos     : {len(photos)}")
    print()

    agent = ArticleAgent(settings)
    result = agent.run(
        brief_text,
        photos=photos,
        doc_type=args.doc_type,
        repair_rounds=args.repair_rounds,
        write_outputs=True,
        output_root=Path(args.out) if args.out else None,
        progress=lambda message: print(f"  · {message}"),
        art_backend=args.art,
        deck=not args.no_deck,
    )

    print()
    print(result.report.text())
    print()
    article = result.article
    title = (article.get("title") or {}).get("cn", "")
    print(f"title   : {title}")
    print(f"outputs : {result.output_dir}")
    print(f"usage   : {result.usage.get('total_tokens', 0)} tokens, "
          f"{result.usage.get('elapsed_s', '?')}s, {result.attempts} attempt(s)")

    needs = article.get("needs_editor") or []
    if needs:
        print("\nFOR THE EDITOR (before 送审):")
        for item in needs:
            print(f"  - {item}")

    if args.strict and not result.report.ok:
        print("\nstrict: exiting non-zero because the check did not pass")
        return 2
    return 0


def cmd_form(args) -> int:
    """Print the intake questions, or generate straight from a filled-in answers file."""
    from . import form

    if args.answers:
        path = Path(args.answers)
        if not path.is_file():
            print(f"no such answers file: {path}", file=sys.stderr)
            return 1
        try:
            answers = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            print(f"{path} is not valid JSON: {exc}", file=sys.stderr)
            return 1
        ok, errors, warnings = form.validate_answers(answers)
        for warning in warnings:
            print(f"note: {warning}")
        if not ok:
            print("the answers are incomplete:", file=sys.stderr)
            for item in errors:
                print(f"  - {item}", file=sys.stderr)
            return 2

        settings = _settings(args)
        photos = collect_photos(args.photo or [])
        print(f"HSIYC article writer — generating from the intake form")
        print(f"  key    : {mask(settings.api_key)}")
        print(f"  photos : {len(photos)}")
        print()
        agent = ArticleAgent(settings)
        result = agent.run_from_answers(
            answers,
            photos=photos,
            repair_rounds=args.repair_rounds,
            write_outputs=True,
            output_root=Path(args.out) if args.out else None,
            progress=lambda message: print(f"  · {message}"),
            art_backend=args.art,
            deck=not args.no_deck,
        )
        print()
        print(result.report.text())
        print(f"\ntitle   : {(result.article.get('title') or {}).get('cn', '')}")
        print(f"outputs : {result.output_dir}")
        needs = result.article.get("needs_editor") or []
        if needs:
            print("\nFOR THE EDITOR (before 送审):")
            for item in needs:
                print(f"  - {item}")
        return 0 if (result.report.ok or not args.strict) else 2

    # No answers file: print the questions, and an example skeleton to fill in.
    print("HSIYC article intake questions")
    print("=" * 60)
    for group in form.field_groups():
        print(f"\n{group['group'].upper()}")
        for f in group["fields"]:
            star = " *" if f["required"] else "  "
            print(f"{star} {f['label']}  [{f['key']}]")
            if f["choices"]:
                for c in f["choices"]:
                    print(f"        - {c['label']}")
            if f["hint"]:
                print(f"      {f['hint']}")
    print("\n" + "=" * 60)
    print("Fill these into a JSON file and run:")
    print(f"  {Path(sys.executable).name} -m hsiyc_writer form --answers answers.json")
    print("\nExample skeleton:")
    print(json.dumps({f.key: "" for f in form.FIELDS if f.required}, ensure_ascii=False, indent=1))
    return 0


def cmd_develop(args) -> int:
    """Improve the operator's rough event description before an article is written."""
    from .deepseek import DeepSeekClient, DeepSeekError
    from .develop import DescriptionError, develop_description

    answers_path: Path | None = None
    if args.answers:
        answers_path = Path(args.answers)
        if not answers_path.is_file():
            print(f"no such answers file: {answers_path}", file=sys.stderr)
            return 1
        try:
            answers = json.loads(answers_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            print(f"{answers_path} is not valid JSON: {exc}", file=sys.stderr)
            return 1
        text = str(answers.get("event_description") or "")
        doc_type = str(answers.get("doc_type") or "")
        if not text.strip():
            print(f"{answers_path} has an empty 'event_description' — nothing to develop.", file=sys.stderr)
            return 2
    elif args.file:
        path = Path(args.file)
        if not path.is_file():
            print(f"no such file: {path}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8-sig")
        doc_type = args.doc_type
    else:
        text = args.text or sys.stdin.read()
        doc_type = args.doc_type

    settings = _settings(args)
    try:
        result = develop_description(DeepSeekClient(settings), text, doc_type)
    except DescriptionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except DeepSeekError as exc:
        print(f"DeepSeek API failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("DEVELOPED DESCRIPTION")
        print("=" * 60)
        print(result["description"])
        stray = result["unsourced"]
        print()
        if stray["numbers"] or stray["names"] or stray["dates"]:
            print("WARNING — this rewrite contains material your notes do not:")
            for number in stray["numbers"]:
                print(f"  figure {number!r}")
            for date in stray["dates"]:
                print(f"  date   {date!r}")
            for name in stray["names"]:
                print(f"  name   {name!r}")
            print("  Remove it, or add the fact to your own notes.")
        else:
            print("Checked: no figure, date or Latin name was added that you did not write.")
        if result["questions"]:
            print("\nAGENTICA STILL NEEDS TO KNOW")
            for question in result["questions"]:
                print(f"  - {question}")
        if result["dropped"]:
            print("\nIT COULD NOT KEEP")
            for item in result["dropped"]:
                print(f"  - {item}")

    if answers_path and args.write:
        answers["event_description"] = result["description"]
        answers_path.write_text(
            json.dumps(answers, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"\nwritten back to {answers_path}", file=sys.stderr)

    # Non-zero when the rewrite would not survive the article check, so a script can stop.
    stray = result["unsourced"]
    return 1 if (stray["numbers"] or stray["names"] or stray["dates"]) else 0


def cmd_wechat(args) -> int:
    """Verify the 公众号 credentials, or create a draft from a bundle (dry run unless --send)."""
    from .wechat import WeChatError, WeChatSettings, check_credentials, create_draft

    settings = WeChatSettings.load()

    if args.check:
        return _wechat_check(settings, check_credentials)

    if not args.bundle:
        print("give a bundle folder, or use --check to test the credentials", file=sys.stderr)
        return 2

    bundle = Path(args.bundle)
    if not bundle.exists():
        print(f"no such bundle: {bundle}", file=sys.stderr)
        return 1
    print("WeChat 公众号 draft")
    print(f"  credentials: {settings.describe()}")
    print(f"  mode       : {'SEND (a draft will be created)' if args.send else 'dry run (nothing leaves this machine)'}")
    if args.send and not settings.configured:
        print("\nCannot send: no 公众号 credentials configured.", file=sys.stderr)
        print("  Run `wechat --check` for the full checklist.", file=sys.stderr)
        return 2
    try:
        result = create_draft(bundle, settings, send=args.send,
                              progress=lambda message: print(f"  · {message}"))
    except WeChatError as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1

    print()
    if result.sent:
        print(f"draft created — open 公众号后台 → 草稿箱 to review and publish")
        print(f"  media_id: {result.draft_media_id}")
    else:
        print("dry run complete — no draft was created")
    for name, url in result.uploaded:
        print(f"  uploaded {name} -> {url}")
    for note in result.notes:
        print(f"  note: {note}")
    print(f"  payload written to {bundle / 'wechat-draft.json'}")
    return 0


def _wechat_check(settings, check_credentials) -> int:
    """`wechat --check`: the one command that tells the club whether the setup is right."""
    print("Checking the 公众号 setup")
    print(f"  appid      : {settings.appid or '(unset)'}")
    print(f"  secret     : {'set' if settings.secret else '(unset)'}")
    print("  calling get access_token …")
    result = check_credentials(settings)
    print(f"  public IP  : {result['public_ip'] or '(lookup failed; check it manually)'}")
    if result["ok"]:
        print(f"  access_token: {result['token']}")
        print("\nOK — the credentials work and this machine's IP is whitelisted.")
        print("Next:  hsiyc_writer wechat output\\<slug>            (dry run)")
        print("       hsiyc_writer wechat output\\<slug> --send     (create the draft)")
        return 0
    print(f"\nFAILED: {result['error']}", file=sys.stderr)
    print("\nSetup checklist (公众号后台 → 设置与开发 → 基本配置):", file=sys.stderr)
    print("  1. copy the AppID and AppSecret into HSIYC_WECHAT_APPID / HSIYC_WECHAT_SECRET,", file=sys.stderr)
    print("     or into hsiyc_writer/.wechat_appid and hsiyc_writer/.wechat_secret", file=sys.stderr)
    print(f"  2. add this machine's public IP ({result['public_ip'] or 'see 我的IP'}) to the IP 白名单", file=sys.stderr)
    print("  3. the account needs the 草稿箱/素材 interface permission — a 未认证 account", file=sys.stderr)
    print("     cannot call it (this shows up as errcode 48001)", file=sys.stderr)
    return 1


def cmd_check(args) -> int:
    """Run the check on an existing article JSON (hand-written drafts included)."""
    path = Path(args.article)
    if not path.is_file():
        print(f"no such file: {path}", file=sys.stderr)
        return 1
    article = json.loads(path.read_text(encoding="utf-8"))

    brief = None
    if args.brief and Path(args.brief).is_file():
        raw = load_brief_file(args.brief)
        try:
            brief = json.loads(raw)
        except json.JSONDecodeError:
            brief = {"raw_notes": raw}

    corpus = Corpus.load()
    report = validate(
        article,
        brief=brief,
        expected_photos=[p.name for p in collect_photos(args.photo or [])],
        corpus_texts=[doc.text for doc in corpus.docs],
        corpus_labels=[doc.slug for doc in corpus.docs],
        require_toc=args.require_toc,
    )
    print(report.text(f"pre-submission check: {path.name}"))
    if args.json:
        out = path.with_suffix(".check.json")
        out.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0 if report.ok else 2


def cmd_corpus(args) -> int:
    corpus = Corpus.load()
    print(f"approved articles loaded: {len(corpus)}")
    kinds = corpus.kinds()
    if kinds:
        print("types: " + ", ".join(f"{k}={v}" for k, v in kinds.items()))
    print()
    for doc in corpus.docs:
        print(f"  [{doc.kind or '—':<6}] {doc.slug}  ({doc.length:,} chars)")
    if args.query:
        print(f"\nnearest to {args.query!r}:")
        for doc, score in corpus.search(args.query, k=5):
            print(f"  {score:.3f}  {doc.slug}")
    return 0


def cmd_key(args) -> int:
    settings = Settings.load(require_key=False)
    print(f"API key   : {mask(settings.api_key)}")
    print(f"base URL  : {settings.base_url}")
    print(f"key file  : {PACKAGE_DIR / '.deepseek_key'}"
          f"{' (present)' if (PACKAGE_DIR / '.deepseek_key').is_file() else ' (absent)'}")
    print(f"env var   : DEEPSEEK_API_KEY{' is set' if settings.api_key else ' is not set'}")
    return 0


def cmd_art(args) -> int:
    """(Re)generate the artwork for an existing bundle, without touching the article."""
    from . import art as artmod

    folder = Path(args.bundle)
    if folder.is_file():
        folder = folder.parent
    slug = folder.name
    article_path = folder / f"{slug}.json"
    if not article_path.is_file():
        candidates = sorted(folder.glob("*.json"))
        candidates = [c for c in candidates if c.name not in {"check_report.json", "run_log.json", "manifest.json"}]
        if len(candidates) != 1:
            print(f"cannot find the article JSON in {folder}", file=sys.stderr)
            return 1
        article_path = candidates[0]

    article = json.loads(article_path.read_text(encoding="utf-8"))
    brief = None
    run_log = folder / "run_log.json"
    if run_log.is_file():
        try:
            brief = json.loads(run_log.read_text(encoding="utf-8")).get("brief")
        except json.JSONDecodeError:
            brief = None

    caps = artmod.capabilities(probe_remote=args.backend in {"auto", "remote"})
    print("artwork")
    print(f"  local renderer : {'yes' if caps.get('local') else 'no'} "
          f"({caps.get('numpy', '?')} / Pillow {caps.get('pillow', '?')})")
    print(f"  CJK font       : {caps.get('cjk_font') or 'none found'}")
    remote_info = caps.get("remote") or {}
    print(f"  online backend : {remote_info.get('provider', '?')} - {remote_info.get('reason', '?')}")
    print(f"  backend        : {args.backend}")

    vibe, evidence = artmod.vibe_for(article, brief)
    print(f"  vibe           : {vibe.key} ({vibe.label_cn}) / motif {vibe.motif} / tone {evidence['tone']}")
    print(f"  matched        : {', '.join(evidence['matched_keywords'][:6]) or '(nothing; house default)'}")
    print()

    manifest = artmod.make_art(
        article, folder / "art", brief=brief, backend=args.backend,
        kinds=tuple(args.kinds) if args.kinds else None,
        seed=args.seed, light=args.light, credit=not args.no_credit,
    )
    for asset in manifest["assets"]:
        print(f"  {asset['file']:<18} {asset['width']}x{asset['height']}  "
              f"{asset['backend']:<20} {asset['caption_cn']}")
    for note in manifest["notes"]:
        print(f"  · {note}")
    print(f"\nwrote {folder / 'art' / 'manifest.json'}")
    return 0


def cmd_tracker(args) -> int:
    """Build the Excel submission tracker across every bundle."""
    from .office_export import OfficeUnavailable, capabilities, export_workbook

    root = Path(args.out) if args.out else OUTPUT_DIR
    if args.bundle:
        bundles = [Path(b) for b in args.bundle]
    else:
        bundles = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    if not bundles:
        print(f"no bundles found under {root}", file=sys.stderr)
        return 1

    target = Path(args.dest) if args.dest else root / "hsiyc-submission-tracker.xlsx"
    caps = capabilities()
    print(f"tracker: {len(bundles)} bundle(s) -> {target}")
    print(f"  openpyxl {'yes' if caps.get('openpyxl') else 'no'}")
    try:
        export_workbook(bundles, target)
    except OfficeUnavailable as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    print(f"wrote {target} ({target.stat().st_size:,} bytes)")
    return 0


def cmd_web(args) -> int:
    from .web import serve

    serve(host=args.host, port=args.port, verbose=args.verbose)
    return 0


def cmd_selftest(args) -> int:
    """Run the offline test suite (no API key needed)."""
    import subprocess

    tests = ["probe_render.py", "validate_cases.py", "form_cases.py", "develop_cases.py",
             "xiumi_cases.py", "wechat_cases.py", "fontcheck.py", "fidelity.py",
             "robustness.py", "art_cases.py", "art_regressions.py", "office_cases.py"]
    failed = []
    for name in tests:
        path = PACKAGE_DIR.parent / "tests" / name
        if not path.is_file():
            print(f"  skip {name} (missing)")
            continue
        proc = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        status = "ok" if proc.returncode == 0 else "FAILED"
        print(f"  {status:<7} {name}")
        if proc.returncode != 0:
            failed.append(name)
            diagnostics = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
            print("\n".join("      " + line for line in diagnostics.splitlines()[-12:]))
    if failed:
        print(f"\n{len(failed)} test file(s) failed: {', '.join(failed)}")
        return 1
    print("\nall offline tests passed")
    return 0


# --------------------------------------------------------------------------- parser
def _add_art_args(parser) -> None:
    """The artwork switches shared by ``generate`` and ``form``."""
    parser.add_argument("--art", default="auto", choices=["auto", "local", "remote", "none"],
                        help="artwork backend: auto tries the online model then draws it "
                             "locally, local never touches the network, remote requires it, "
                             "none skips the artwork (default auto)")
    parser.add_argument("--no-deck", action="store_true",
                        help="skip the .pptx presentation deck")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hsiyc_writer",
        description="Write HSIYC event articles in the approved bilingual style.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write one article from a brief")
    gen.add_argument("-b", "--brief", required=True, help="brief file (.md/.txt/.json)")
    gen.add_argument("-p", "--photo", action="append", default=[],
                     help="photo file or directory (repeatable)")
    gen.add_argument("-t", "--doc-type", default="", help="预告/招募/回顾/收官/喜报/竞赛/活动")
    gen.add_argument("-r", "--repair-rounds", type=int, default=1,
                     help="targeted repair passes after a failed check (default 1)")
    gen.add_argument("-o", "--out", default="", help=f"output root (default {OUTPUT_DIR})")
    gen.add_argument("--model", default="", help="override the text model")
    gen.add_argument("--no-vision", action="store_true", help="do not send photos to the model")
    gen.add_argument("--strict", action="store_true", help="exit non-zero if the check fails")
    _add_art_args(gen)
    gen.set_defaults(func=cmd_generate)

    chk = sub.add_parser("check", help="run the pre-submission check on an article JSON")
    chk.add_argument("article", help="article JSON produced by generate")
    chk.add_argument("-b", "--brief", default="", help="brief file, for number cross-checking")
    chk.add_argument("-p", "--photo", action="append", default=[], help="expected photos")
    chk.add_argument("--require-toc", action="store_true", help="require the TOC card")
    chk.add_argument("--json", action="store_true", help="also write <name>.check.json")
    chk.set_defaults(func=cmd_check)

    corp = sub.add_parser("corpus", help="list the approved articles used as exemplars")
    corp.add_argument("-q", "--query", default="", help="show the nearest articles to this text")
    corp.set_defaults(func=cmd_corpus)

    frm = sub.add_parser("form", help="print the intake questions, or generate from an answers JSON")
    frm.add_argument("-a", "--answers", default="", help="filled-in answers JSON -> generate an article")
    frm.add_argument("-p", "--photo", action="append", default=[], help="photo file or directory")
    frm.add_argument("-r", "--repair-rounds", type=int, default=1)
    frm.add_argument("-o", "--out", default="", help=f"output root (default {OUTPUT_DIR})")
    frm.add_argument("--model", default="", help="override the text model")
    frm.add_argument("--no-vision", action="store_true", help="do not send photos to the model")
    frm.add_argument("--strict", action="store_true", help="exit non-zero if the check fails")
    _add_art_args(frm)
    frm.set_defaults(func=cmd_form)

    dev = sub.add_parser("develop", help="improve a rough event description before writing")
    dev.add_argument("-t", "--text", default="", help="the rough notes")
    dev.add_argument("-f", "--file", default="", help="read the notes from a file")
    dev.add_argument("-a", "--answers", default="", help="develop the event_description in an answers JSON")
    dev.add_argument("-w", "--write", action="store_true",
                     help="with --answers: write the improved text back into the file")
    dev.add_argument("--doc-type", default="", help="预告/招募/回顾/收官/喜报/竞赛/活动")
    dev.add_argument("--json", action="store_true", help="print the raw result as JSON")
    dev.add_argument("--model", default="", help="override the text model")
    dev.add_argument("--offline", action="store_true", help=argparse.SUPPRESS)
    dev.set_defaults(func=cmd_develop)

    wx = sub.add_parser("wechat", help="create a 公众号 draft from a bundle (dry run by default)")
    wx.add_argument("bundle", nargs="?", default="", help="bundle folder (e.g. output/my-event)")
    wx.add_argument("--check", action="store_true",
                    help="test the AppID/AppSecret and the IP whitelist with a real API call")
    wx.add_argument("--send", action="store_true",
                    help="actually create the draft (default: dry run, nothing is sent)")
    wx.set_defaults(func=cmd_wechat)

    art = sub.add_parser("art", help="(re)generate posters and banners for an existing bundle")
    art.add_argument("bundle", help="bundle folder (e.g. output/my-event) or a file inside it")
    art.add_argument("--backend", default="local", choices=["auto", "local", "remote"],
                     help="local draws offline (default); auto tries the online model first")
    art.add_argument("--kind", dest="kinds", action="append", default=[],
                     choices=["banner", "cover", "poster", "social", "dividers"],
                     help="render only these assets (repeatable)")
    art.add_argument("--seed", type=int, default=None, help="pin the random seed")
    art.add_argument("--light", action="store_true", help="print-friendly light background")
    art.add_argument("--no-credit", action="store_true",
                     help="omit the 'AI-generated artwork' provenance line")
    art.set_defaults(func=cmd_art)

    track = sub.add_parser("tracker", help="build the Excel submission tracker across bundles")
    track.add_argument("-b", "--bundle", action="append", default=[],
                       help="bundle folder (repeatable; default: every folder under output/)")
    track.add_argument("-o", "--out", default="", help=f"output root (default {OUTPUT_DIR})")
    track.add_argument("-d", "--dest", default="", help="path of the .xlsx to write")
    track.set_defaults(func=cmd_tracker)

    key = sub.add_parser("key", help="show the configured API key (masked)")
    key.set_defaults(func=cmd_key)

    web = sub.add_parser("web", help="start the browser UI")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("-v", "--verbose", action="store_true", help="log every request")
    web.set_defaults(func=cmd_web)

    selftest = sub.add_parser("selftest", help="run the offline test suite")
    selftest.set_defaults(func=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
