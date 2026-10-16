"""Tiny dependency-free web UI for the agent.

Standard-library HTTP server, so there is nothing to install. One page:

    brief (free text) + document type + event photos
        -> POST /api/generate
        -> DeepSeek drafts the bilingual article
        -> the validator grades it
        -> the bundle lands in output/<slug>/ and the page shows the check report

Generation takes tens of seconds, so the POST streams progress lines and the page
polls for them.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import form, validate
from .config import OUTPUT_DIR, PACKAGE_DIR, UPLOAD_DIR, Settings, ensure_dirs, mask
from .deepseek import DeepSeekClient, DeepSeekError
from .develop import DescriptionError, develop_description
from .pipeline import SUPPORTED_PHOTOS, ArticleAgent
from .retrieval import Corpus

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
PAGE = PACKAGE_DIR / "web" / "form.html"
LEGACY_PAGE = PACKAGE_DIR / "web" / "index.html"
GALLERY_PAGE = PACKAGE_DIR / "web" / "gallery.html"


@dataclass
class Job:
    """One in-flight or finished generation."""

    id: str
    status: str = "running"          # running | done | error
    progress: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str = ""
    output_dir: str = ""

    def note(self, message: str) -> None:
        self.progress.append(message)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job = Job(id=uuid.uuid4().hex[:12])
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


def _multipart_boundary(content_type: str) -> bytes | None:
    match = re.search(r'boundary="?([^";]+)"?', content_type or "")
    return match.group(1).encode("latin-1") if match else None


def parse_multipart(body: bytes, boundary: bytes) -> tuple[dict[str, str], dict[str, bytes]]:
    """Minimal multipart/form-data parser: enough for text fields plus file uploads."""
    fields: dict[str, str] = {}
    files: dict[str, bytes] = {}
    delimiter = b"--" + boundary
    for raw_part in body.split(delimiter):
        if not raw_part or raw_part in (b"--\r\n", b"--", b"\r\n"):
            continue
        part = raw_part
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        head, _, content = part.partition(b"\r\n\r\n")
        if not _:
            continue
        disposition = ""
        for line in head.decode("utf-8", "replace").split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disposition = line
        name_match = re.search(r'name="([^"]*)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if filename_match and filename_match.group(1):
            files[Path(filename_match.group(1)).name] = content
        else:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files


class Handler(BaseHTTPRequestHandler):
    server_version = "HSIYCWriter/0.1"
    jobs = JobStore()
    settings: Settings | None = None
    corpus: Corpus | None = None

    # ------------------------------------------------------------------ plumbing
    def log_message(self, fmt: str, *args) -> None:  # keep the console readable
        if self.server.verbose:  # type: ignore[attr-defined]
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, content_type: str = "application/json; charset=utf-8",
              extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    # ---------------------------------------------------------------------- GET
    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route in ("/", "/index.html", "/form"):
            page = PAGE if PAGE.is_file() else LEGACY_PAGE
            if not page.is_file():
                self._send(500, b"web/form.html is missing", "text/plain; charset=utf-8")
                return
            self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            return

        if route == "/legacy":
            # The original free-form brief page, kept for pasting long notes.
            if LEGACY_PAGE.is_file():
                self._send(200, LEGACY_PAGE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._json(404, {"error": "legacy page not available"})
            return

        if route in ("/gallery", "/gallery.html"):
            # Everything the club has produced, with the artwork, so past posters
            # can be found again without digging through folders.
            if GALLERY_PAGE.is_file():
                self._send(200, GALLERY_PAGE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._json(404, {"error": "gallery page not available"})
            return

        if route == "/api/bundles":
            self._list_bundles()
            return

        if route == "/api/form":
            self._json(200, {
                "groups": form.field_groups(),
                "credit_roles": list(validate.CREDIT_ROLES),
                "article_types": list(form.ARTICLES),
                "art_backends": [
                    {"value": "auto", "label": "AI illustration, else house vector art (尝试在线生成，失败则本地绘制)"},
                    {"value": "local", "label": "House vector art, drawn offline (本地绘制，不联网)"},
                    {"value": "remote", "label": "AI illustration only, fail if offline (仅在线生成)"},
                    {"value": "none", "label": "No artwork (不生成插画)"},
                ],
            })
            return

        if route.startswith("/api/paste/"):
            self._serve_paste(route[len("/api/paste/"):])
            return

        if route == "/api/status":
            settings = self.settings or Settings.load(require_key=False)
            corpus = self.corpus
            from . import art as artmod
            from .wechat import WeChatSettings

            wechat = WeChatSettings.load()
            self._json(200, {
                "key_present": bool(settings.api_key),
                "key_masked": mask(settings.api_key),
                "text_model": settings.text_model,
                "vision_model": settings.vision_model,
                "vision_enabled": settings.vision_enabled,
                "corpus_size": len(corpus) if corpus else 0,
                "output_dir": str(OUTPUT_DIR),
                # The page only offers "create a WeChat draft" when the club has configured
                # the 公众号 credentials; the secret itself never leaves the server.
                "wechat_configured": wechat.configured,
                "wechat_appid": wechat.appid if wechat.configured else "",
                "art": artmod.capabilities(),
            })
            return

        if route.startswith("/api/job/"):
            job = self.jobs.get(route.rsplit("/", 1)[-1])
            if not job:
                self._json(404, {"error": "unknown job"})
                return
            self._json(200, {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "error": job.error,
                "output_dir": job.output_dir,
                "result": job.result,
            })
            return

        if route == "/api/files":
            self._list_files(urlparse(self.path).query)
            return

        if route.startswith("/file/"):
            self._serve_output(route[len("/file/") :])
            return

        self._json(404, {"error": "not found"})

    def _serve_paste(self, slug: str) -> None:
        """``/api/paste/<slug>`` - the paste markup as a URL another tool can pull.

        This is the closest thing to "linking Agentica to 秀米": there is no 秀米 API to call,
        but anything running in the operator's own logged-in browser - a bookmarklet, a
        userscript - can fetch this and insert it into the 秀米 editor. Cross-origin by
        design, so it carries CORS headers; browsers also require the private-network header
        before allowing a public page (xiumi.us) to reach 127.0.0.1 at all.
        """
        slug = slug.strip().strip("/")
        if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
            self._json(400, {"error": "bad slug"})
            return
        folder = (OUTPUT_DIR / slug).resolve()
        try:
            folder.relative_to(OUTPUT_DIR.resolve())
        except ValueError:
            self._json(403, {"error": "outside the output directory"})
            return
        if not folder.is_dir():
            self._json(404, {"error": "no such bundle"})
            return

        from .render import to_xiumi_html, to_xiumi_notes

        article = None
        for candidate in (folder / f"{slug}.json", *sorted(folder.glob("*.json"))):
            if candidate.name in ("check_report.json", "wechat-draft.json") or not candidate.is_file():
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, dict) and data.get("sections"):
                article = data
                break
        if article is None:
            self._json(404, {"error": f"no article JSON in {folder.name}"})
            return

        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        if urlparse(self.path).query == "meta":
            self._json(200, {
                "slug": slug,
                "title": (article.get("title") or {}).get("cn", ""),
                "guide": to_xiumi_notes(article, slug),
                "chars": len(to_xiumi_html(article)),
            })
            return
        self._send(200, to_xiumi_html(article).encode("utf-8"),
                   "text/html; charset=utf-8", headers)

    def _list_bundles(self) -> None:
        """Summarise every generated bundle, for the gallery page.

        Reads only what a bundle already contains, and treats every file as
        optional: a half-written or hand-made folder shows up with blanks rather
        than breaking the page.
        """
        from .art import load_manifest

        items: list[dict] = []
        if OUTPUT_DIR.is_dir():
            for folder in sorted(p for p in OUTPUT_DIR.iterdir() if p.is_dir()):
                slug = folder.name
                article_path = folder / f"{slug}.json"
                if not article_path.is_file():
                    continue
                try:
                    article = json.loads(article_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                meta = article.get("meta") or {}
                title = article.get("title") or {}

                report: dict = {}
                report_path = folder / "check_report.json"
                if report_path.is_file():
                    try:
                        report = json.loads(report_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        report = {}

                manifest = load_manifest(folder / "art") or {}
                poster = next((a for a in manifest.get("assets", []) if a.get("kind") == "poster"), None)
                try:
                    files = sorted(p.name for p in folder.iterdir() if p.is_file())
                except OSError:
                    files = []

                items.append({
                    "slug": slug,
                    "title_cn": title.get("cn", ""),
                    "title_en": title.get("en", ""),
                    "doc_type": meta.get("doc_type", ""),
                    "event_date": meta.get("event_date", ""),
                    "venue": meta.get("venue", ""),
                    "score": report.get("score"),
                    "errors": report.get("errors"),
                    "warnings": report.get("warnings"),
                    "vibe": (manifest.get("vibe") or {}).get("key", ""),
                    "vibe_label": (manifest.get("vibe") or {}).get("label_cn", ""),
                    "art_backend": manifest.get("backend", ""),
                    "poster": f"/file/{slug}/art/{poster['file']}" if poster else "",
                    "files": files,
                })
        items.sort(key=lambda item: (str(item["event_date"]), item["slug"]), reverse=True)
        self._json(200, {"bundles": items, "root": str(OUTPUT_DIR), "count": len(items)})

    def _list_files(self, query: str) -> None:
        """List the deliverables in one run's output folder, for the results panel."""
        from urllib.parse import parse_qs

        raw = (parse_qs(query).get("dir") or [""])[0]
        if not raw:
            self._json(400, {"error": "dir is required"})
            return
        try:
            folder = Path(raw).resolve()
            folder.relative_to(OUTPUT_DIR.resolve())
        except (ValueError, OSError):
            self._json(403, {"error": "outside the output directory"})
            return
        if not folder.is_dir():
            self._json(404, {"error": "no such folder"})
            return
        order = {"preview.html": 0, "docx": 1, "pdf": 2, "md": 3, "json": 4, "txt": 5}
        files = []
        for item in sorted([*folder.iterdir(), *(folder / "art").glob("*.png"), *(folder / "art").glob("manifest.json")]):
            if not item.is_file() or item.name.startswith("run_log"):
                continue
            try:
                item.resolve().relative_to(OUTPUT_DIR.resolve())
            except ValueError:
                continue
            rank = next((v for k, v in order.items() if item.name.endswith(k)), 9)
            files.append((rank, item.relative_to(OUTPUT_DIR.resolve()).as_posix()))
        self._json(200, {"files": [name for _, name in sorted(files)]})

    def _serve_output(self, relative: str) -> None:
        """Serve a file from the output directory (never escapes it)."""
        target = (OUTPUT_DIR / relative).resolve()
        try:
            target.relative_to(OUTPUT_DIR.resolve())
        except ValueError:
            self._json(403, {"error": "path outside the output directory"})
            return
        if not target.is_file():
            self._json(404, {"error": "no such file"})
            return
        suffix = target.suffix.lower()
        types = {
            ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        }
        self._send(200, target.read_bytes(), types.get(suffix, "application/octet-stream"))

    # --------------------------------------------------------------------- POST
    def do_OPTIONS(self) -> None:  # noqa: N802
        """Preflight for the cross-origin paste endpoint.

        A page on xiumi.us fetching 127.0.0.1 is a private-network request: Chrome asks the
        user once for permission, and only after the response carries this header.
        """
        route = urlparse(self.path).path
        if not route.startswith("/api/paste/"):
            self._json(404, {"error": "not found"})
            return
        self._send(204, b"", "text/plain; charset=utf-8", {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Private-Network": "true",
            "Access-Control-Max-Age": "600",
        })

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/api/form/validate":
            self._validate_form()
            return
        if route == "/api/generate-form":
            self._accept_form()
            return
        if route == "/api/develop":
            self._develop_description()
            return
        if route == "/api/wechat-draft":
            self._wechat_draft()
            return
        if route == "/api/wechat-check":
            self._wechat_check()
            return
        if route == "/api/generate":
            self._accept_legacy()
            return
        self._json(404, {"error": "not found"})

    # ------------------------------------------------------------ form endpoints
    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._json(400, {"error": "empty request body"})
            return None
        if length > MAX_UPLOAD_BYTES:
            self._json(413, {"error": f"upload too large ({length} bytes; limit {MAX_UPLOAD_BYTES})"})
            return None
        return self.rfile.read(length)

    def _validate_form(self) -> None:
        """Check the answers without generating, so the page can flag missing fields."""
        body = self._read_body()
        if body is None:
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"error": f"invalid JSON: {exc}"})
            return
        answers = payload.get("answers") or {}
        ok, errors, warnings = form.validate_answers(answers)
        missing_keys = [
            f.key for f in form.FIELDS
            if f.required and not str(answers.get(f.key) or "").strip()
        ]
        self._json(200, {
            "ok": ok,
            "errors": errors,
            "warnings": warnings,
            "required_keys": missing_keys,
        })

    def _develop_description(self) -> None:
        """Improve the operator's rough event description, without generating an article.

        One short API call on the page's own thread pool: the operator presses a button,
        reads the result and edits it, and only then spends the tokens for a full article.
        """
        body = self._read_body()
        if body is None:
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"error": f"invalid JSON: {exc}"})
            return

        text = str(payload.get("text") or "")
        doc_type = str(payload.get("doc_type") or "").strip()

        settings = self.settings or Settings.load()
        if not settings.api_key:
            self._json(400, {"error": "no DeepSeek API key configured"})
            return

        try:
            result = develop_description(DeepSeekClient(settings), text, doc_type)
        except DescriptionError as exc:
            self._json(400, {"error": str(exc)})
            return
        except DeepSeekError as exc:
            self._json(502, {"error": f"DeepSeek API failed: {exc}"})
            return
        except Exception as exc:  # never take the server down for a rewrite
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
            return

        self._json(200, result)

    def _wechat_check(self) -> None:
        """Ask WeChat for a token: the one call that proves the 公众号 setup is right.

        Runs on the handler thread - it is a single request, and the answer (bad AppID,
        missing IP whitelist, no interface permission) is what the operator needs to see
        before trying to send an article.
        """
        from .wechat import WeChatSettings, check_credentials

        settings = WeChatSettings.load()
        try:
            result = check_credentials(settings)
        except Exception as exc:  # never take the server down for a setup check
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return
        result["configured"] = settings.configured
        self._json(200 if result.get("ok") else 400, result)

    def _wechat_draft(self) -> None:
        """Create (or dry-run) a 公众号 draft for a finished bundle.

        The bundle folder is resolved inside the output directory, so a request cannot
        reach anywhere else. `send` must be explicit: creating a draft is external state
        in the club's account, and a stray click must not leave one behind.
        """
        body = self._read_body()
        if body is None:
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"error": f"invalid JSON: {exc}"})
            return

        raw = str(payload.get("dir") or "").strip()
        send = bool(payload.get("send"))
        if not raw:
            self._json(400, {"error": "dir is required"})
            return
        try:
            bundle = Path(raw).resolve()
            bundle.relative_to(OUTPUT_DIR.resolve())
        except (ValueError, OSError):
            self._json(403, {"error": "outside the output directory"})
            return
        if not bundle.is_dir():
            self._json(404, {"error": "no such bundle"})
            return

        from .wechat import WeChatError, WeChatSettings, create_draft

        settings = WeChatSettings.load()
        if send and not settings.configured:
            self._json(400, {
                "error": "No 公众号 credentials. Set HSIYC_WECHAT_APPID and HSIYC_WECHAT_SECRET, "
                         "and add this machine's public IP to the 公众号 IP 白名单.",
            })
            return

        progress: list[str] = []
        try:
            result = create_draft(bundle, settings, send=send, progress=progress.append)
        except WeChatError as exc:
            self._json(502, {"error": str(exc), "progress": progress})
            return
        except Exception as exc:  # never take the server down for a draft
            self._json(500, {"error": f"{type(exc).__name__}: {exc}", "progress": progress})
            return

        self._json(200, {
            "ok": True,
            "sent": result.sent,
            "draft_media_id": result.draft_media_id,
            "cover_media_id": result.cover_media_id,
            "uploaded": len(result.uploaded),
            "notes": result.notes,
            "progress": progress,
            "configured": settings.configured,
        })

    def _accept_form(self) -> None:
        """Validate the answers, store the photos and start a generation job."""
        body = self._read_body()
        if body is None:
            return
        boundary = _multipart_boundary(self.headers.get("Content-Type", ""))
        if not boundary:
            self._json(400, {"error": "expected multipart/form-data"})
            return
        fields, files = parse_multipart(body, boundary)

        try:
            answers = json.loads(fields.get("answers") or "{}")
        except json.JSONDecodeError as exc:
            self._json(400, {"error": f"answers were not valid JSON: {exc}"})
            return
        if not isinstance(answers, dict):
            self._json(400, {"error": "answers must be an object"})
            return

        ok, errors, warnings = form.validate_answers(answers)
        if not ok:
            self._json(400, {"error": " ".join(errors), "errors": errors, "warnings": warnings})
            return

        repair_rounds = 1
        try:
            repair_rounds = max(0, min(2, int(fields.get("repair_rounds") or 1)))
        except ValueError:
            pass

        art_backend = str(fields.get("art") or "auto").strip().lower()
        if art_backend not in {"auto", "local", "remote", "none"}:
            art_backend = "auto"
        deck = str(fields.get("deck") or "1").strip() not in {"0", "false", "no"}

        settings = self.settings or Settings.load()
        if not settings.api_key:
            self._json(400, {"error": "no DeepSeek API key configured"})
            return

        job = self.jobs.create()
        photo_paths = self._store_uploads(job, files)
        job.note(f"saved {len(photo_paths)} photo(s)")
        for warning in warnings:
            job.note(f"note: {warning}")

        thread = threading.Thread(
            target=self._run_form_job,
            args=(job, settings, answers, photo_paths, repair_rounds, art_backend, deck),
            daemon=True,
        )
        thread.start()
        self._json(200, {"job_id": job.id, "warnings": warnings})

    def _run_form_job(
        self,
        job: Job,
        settings: Settings,
        answers: dict,
        photos: list[Path],
        repair_rounds: int,
        art_backend: str = "auto",
        deck: bool = True,
    ) -> None:
        try:
            agent = ArticleAgent(settings, corpus=self.corpus)
            result = agent.run_from_answers(
                answers,
                photos=photos,
                repair_rounds=repair_rounds,
                write_outputs=True,
                progress=job.note,
                art_backend=art_backend,
                deck=deck,
            )
            job.result = self._result_payload(result)
            job.output_dir = str(result.output_dir or "")
            job.status = "done"
        except Exception as exc:  # surface the failure in the UI instead of dying
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "error"

    @staticmethod
    def _result_payload(result) -> dict:
        # The paste markup travels with the result so the page can put it on the clipboard
        # from a plain click. Fetching it in the click handler first - which is what the
        # button used to do - spends the user gesture before the clipboard call, and Safari
        # and some webviews refuse a write that arrives after an await.
        from .render import to_xiumi_html

        return {
            "article": result.article,
            "check": result.report.as_dict(),
            "exemplars": result.exemplars,
            "usage": result.usage,
            "attempts": result.attempts,
            "needs_editor": result.article.get("needs_editor", []),
            "photo_report": result.photo_report,
            "brief_text": result.brief_text,
            "xiumi_html": to_xiumi_html(result.article),
            "log": result.log,
            "art": Handler._art_payload(result),
        }

    @staticmethod
    def _art_payload(result) -> dict | None:
        """The artwork manifest plus browser URLs, for the results gallery.

        A failure here must never be silent. ``make_bundle_art`` deliberately
        swallows exceptions so artwork cannot cost the club its article - which
        makes this the only place that can tell the operator that the pictures on
        screen are missing, or left over from an earlier run.
        """
        from .art import load_manifest

        folder = getattr(result, "output_dir", None)
        if not folder:
            return None
        folder = Path(folder)

        run_log: dict = {}
        log_path = folder / "run_log.json"
        if log_path.is_file():
            try:
                run_log = json.loads(log_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                run_log = {}
        error = str(run_log.get("art_error") or "")
        manifest = load_manifest(folder / "art")

        if not manifest:
            return {"error": error, "assets": []} if error else None

        slug = folder.name
        payload = dict(manifest)
        payload["assets"] = [
            {**asset, "url": f"/file/{slug}/art/{asset.get('file', '')}"}
            for asset in manifest.get("assets", [])
        ]
        if error:
            payload["error"] = error
        # This run recorded no artwork, yet a manifest exists on disk: what the
        # reviewer is looking at came from an earlier generation. Saying so is
        # the difference between trusting the picture and being misled by it.
        payload["stale"] = run_log.get("art") is None
        return payload

    # ---------------------------------------------------------- legacy endpoint
    def _accept_legacy(self) -> None:
        body = self._read_body()
        if body is None:
            return

        boundary = _multipart_boundary(self.headers.get("Content-Type", ""))
        if not boundary:
            self._json(400, {"error": "expected multipart/form-data"})
            return
        fields, files = parse_multipart(body, boundary)

        brief = (fields.get("brief") or "").strip()
        if len(brief) < 30:
            self._json(400, {"error": "请填写活动信息（至少 30 个字符）/ the brief is too short"})
            return

        doc_type = (fields.get("doc_type") or "").strip()
        repair_rounds = 1
        try:
            repair_rounds = max(0, min(2, int(fields.get("repair_rounds") or 1)))
        except ValueError:
            pass

        settings = self.settings or Settings.load()
        if not settings.api_key:
            self._json(400, {"error": "no DeepSeek API key configured"})
            return

        job = self.jobs.create()
        photo_paths = self._store_uploads(job, files)
        job.note(f"saved {len(photo_paths)} photo(s)")

        thread = threading.Thread(
            target=self._run_job,
            args=(job, settings, brief, doc_type, photo_paths, repair_rounds),
            daemon=True,
        )
        thread.start()
        self._json(200, {"job_id": job.id})

    def _store_uploads(self, job: Job, files: dict[str, bytes]) -> list[Path]:
        folder = UPLOAD_DIR / job.id
        folder.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for raw_name, blob in files.items():
            name = Path(raw_name).name
            if Path(name).suffix.lower() not in SUPPORTED_PHOTOS:
                job.note(f"skipped {name}: unsupported image type")
                continue
            target = folder / name
            target.write_bytes(blob)
            paths.append(target)
        return sorted(paths)

    def _run_job(
        self,
        job: Job,
        settings: Settings,
        brief: str,
        doc_type: str,
        photos: list[Path],
        repair_rounds: int,
    ) -> None:
        try:
            agent = ArticleAgent(settings, corpus=self.corpus)
            result = agent.run(
                brief,
                photos=photos,
                doc_type=doc_type,
                repair_rounds=repair_rounds,
                write_outputs=True,
                progress=job.note,
            )
            job.result = self._result_payload(result)
            job.output_dir = str(result.output_dir or "")
            job.status = "done"
        except Exception as exc:  # surface the failure in the UI instead of dying
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "error"


def serve(host: str = "127.0.0.1", port: int = 8765, verbose: bool = False) -> None:
    ensure_dirs()
    Handler.settings = Settings.load(require_key=False)
    Handler.corpus = Corpus.load()
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.verbose = verbose  # type: ignore[attr-defined]
    print(f"HSIYC article writer  ->  http://{host}:{port}")
    print(f"  approved corpus : {len(Handler.corpus)} article(s)")
    print(f"  API key         : {mask(Handler.settings.api_key)}")
    print(f"  outputs         : {OUTPUT_DIR}")
    print("  Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
