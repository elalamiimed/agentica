"""Send the finished article straight into the 公众号 draft box.

秀米 has no import, and its 一键同步 needs a human to scan an authorisation QR code. But
the thing 秀米 does behind that button is the **official** WeChat server API, and the club
can call it directly: upload each photo to get a `mmbiz.qpic.cn` URL, upload a cover as a
permanent material, then create a draft whose `content` is HTML. That removes the layout
step for everything except the club's own 秀米 template - and the article we already
produce is exactly the markup that API accepts (inline styles, `<section>`, no
stylesheet), which is why this module is short.

Endpoints, per the official documentation:

===========================  ===========================================================
token                        ``GET  /cgi-bin/token?grant_type=client_credential``
image inside the article     ``POST /cgi-bin/media/uploadimg``       (multipart ``media``)
cover image (permanent)      ``POST /cgi-bin/material/add_material?type=image``
create the draft             ``POST /cgi-bin/draft/add``
===========================  ===========================================================

What the club has to provide, or none of it works:

* **AppID and AppSecret** - 公众号后台 → 设置与开发 → 基本配置.
* **This machine's public IP in the IP 白名单** - same page. WeChat answers
  ``errcode 40164`` until it is there.
* An account with the **draft / material interface permission**. The draft interface is
  available to 公众号 and 服务号; a 未认证 account generally cannot call it.

Everything here is offline-testable: the client takes a transport, and the tests pass a
fake one. ``--send`` is what actually talks to WeChat, and it needs the credentials.
"""

from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import PACKAGE_DIR

WECHAT_BASE = "https://api.weixin.qq.com"

# WeChat's own limits, from the interface documentation.
TITLE_MAX = 32
AUTHOR_MAX = 16
DIGEST_MAX = 120
DIGEST_CHARS = 54          # what WeChat itself takes when no digest is given
CONTENT_MAX_BYTES = 1024 * 1024
IMAGE_MAX_BYTES = 1024 * 1024
IMAGE_MAX_PX = 2048

# access_token lives 7200s; renew early so a long upload run cannot expire mid-way.
TOKEN_TTL = 7200 - 300


class WeChatError(RuntimeError):
    """A call failed, or the club has not configured the account."""

    def __init__(self, message: str, code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


@dataclass
class WeChatSettings:
    """The 公众号 credentials. Never hard-coded, never printed in full."""

    appid: str = ""
    secret: str = ""
    base_url: str = WECHAT_BASE
    timeout: int = 60

    @classmethod
    def load(cls) -> "WeChatSettings":
        return cls(
            appid=os.environ.get("HSIYC_WECHAT_APPID", "").strip() or _key_file("wechat_appid"),
            secret=os.environ.get("HSIYC_WECHAT_SECRET", "").strip() or _key_file("wechat_secret"),
            base_url=os.environ.get("HSIYC_WECHAT_BASE", WECHAT_BASE).rstrip("/"),
        )

    @property
    def configured(self) -> bool:
        return bool(self.appid and self.secret)

    def describe(self) -> str:
        if not self.configured:
            return "not configured (set HSIYC_WECHAT_APPID and HSIYC_WECHAT_SECRET)"
        return f"appid {self.appid[:6]}… secret …{self.secret[-4:]}"


def _key_file(name: str) -> str:
    path = PACKAGE_DIR / f".{name}"
    if path.is_file():
        return path.read_text(encoding="utf-8-sig").strip()
    return ""


# --------------------------------------------------------------------------- transport
class UrllibTransport:
    """The real network, behind an interface the tests can replace."""

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout

    def get_json(self, url: str) -> dict:
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, url: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_file(self, url: str, content: bytes, filename: str, field_name: str = "media") -> dict:
        boundary = "----HSIYC" + uuid.uuid4().hex
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body = bytearray()
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8")
        )
        body.extend(content)
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        request = urllib.request.Request(
            url, data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


# ------------------------------------------------------------------------------ client
class WeChatClient:
    """Token caching, image uploads and draft creation for one 公众号."""

    def __init__(self, settings: WeChatSettings, transport: Any | None = None) -> None:
        self.s = settings
        self.transport = transport or UrllibTransport(settings.timeout)
        self._token = ""
        self._token_expiry = 0.0
        self.log: list[str] = []

    # ------------------------------------------------------------------ internals
    def _note(self, message: str) -> None:
        self.log.append(message)

    def _check(self, payload: dict, what: str) -> dict:
        code = payload.get("errcode") or 0
        if code:
            message = str(payload.get("errmsg") or "")
            hint = {
                40164: "this machine's IP is not in the 公众号 IP 白名单 "
                       "(公众号后台 → 设置与开发 → 基本配置 → IP白名单)",
                40013: "invalid AppID",
                40125: "invalid AppSecret",
                40001: "the AppSecret is wrong, or the token is stale — check it against "
                       "设置与开发 → 基本配置",
                40243: "the AppSecret has been frozen (a security setting an admin can toggle "
                       "on the same page). Freezing does not affect 秀米's 授权 sync — only "
                       "this direct API route — so it can be unfrozen just for the setup, or "
                       "left frozen and 秀米 used instead.",
                50007: "the 公众号 account itself is frozen",
                50004: "this account type may not call the token interface",
                48001: "this 公众号 does not have the interface permission "
                       "(a 未认证 account cannot call the draft interface)",
                40005: "WeChat rejected the image format (jpg/png only)",
                40009: "WeChat rejected the image size (must be under 1 MB)",
            }.get(code, "")
            raise WeChatError(
                f"{what} failed: errcode {code} {message}" + (f" — {hint}" if hint else ""),
                code, payload,
            )
        return payload

    def token(self, force: bool = False) -> str:
        """A cached access_token. WeChat allows 7200s; renew with a safety margin."""
        if not self.s.configured:
            raise WeChatError(
                "No 公众号 credentials. Set HSIYC_WECHAT_APPID and HSIYC_WECHAT_SECRET "
                "(公众号后台 → 设置与开发 → 基本配置)."
            )
        if self._token and not force and time.time() < self._token_expiry:
            return self._token
        query = urllib.parse.urlencode({
            "grant_type": "client_credential", "appid": self.s.appid, "secret": self.s.secret,
        })
        payload = self._check(self.transport.get_json(f"{self.s.base_url}/cgi-bin/token?{query}"),
                              "获取 access_token")
        token = str(payload.get("access_token") or "")
        if not token:
            raise WeChatError("WeChat returned no access_token", None, payload)
        self._token = token
        self._token_expiry = time.time() + TOKEN_TTL
        self._note("access_token acquired (cached for ~1h55m)")
        return token

    # -------------------------------------------------------------------- uploading
    def upload_content_image(self, path: Path) -> str:
        """Upload one photo for use inside the article body; returns its ``mmbiz`` URL."""
        content, filename = prepare_image(path)
        query = urllib.parse.urlencode({"access_token": self.token()})
        payload = self._check(
            self.transport.post_file(f"{self.s.base_url}/cgi-bin/media/uploadimg?{query}",
                                     content, filename),
            f"uploading {Path(path).name}",
        )
        url = str(payload.get("url") or "")
        if not url:
            raise WeChatError(f"WeChat returned no url for {Path(path).name}", None, payload)
        self._note(f"uploaded {Path(path).name} ({len(content):,} bytes) -> {url[:64]}…")
        return url

    def upload_cover(self, path: Path) -> str:
        """Upload the cover as a *permanent* material; the draft needs its media_id."""
        content, filename = prepare_image(path)
        query = urllib.parse.urlencode({"access_token": self.token(), "type": "image"})
        payload = self._check(
            self.transport.post_file(f"{self.s.base_url}/cgi-bin/material/add_material?{query}",
                                     content, filename),
            f"uploading cover {Path(path).name}",
        )
        media_id = str(payload.get("media_id") or "")
        if not media_id:
            raise WeChatError(f"WeChat returned no media_id for {Path(path).name}", None, payload)
        self._note(f"cover uploaded ({len(content):,} bytes) -> media_id {media_id[:24]}…")
        return media_id

    # ------------------------------------------------------------------------ draft
    def add_draft(self, payload: dict) -> str:
        query = urllib.parse.urlencode({"access_token": self.token()})
        result = self._check(
            self.transport.post_json(f"{self.s.base_url}/cgi-bin/draft/add?{query}", payload),
            "creating the draft",
        )
        media_id = str(result.get("media_id") or "")
        if not media_id:
            raise WeChatError("WeChat returned no draft media_id", None, result)
        self._note(f"draft created -> media_id {media_id}")
        return media_id


# ------------------------------------------------------------------------ image prep
def prepare_image(path: Path) -> tuple[bytes, str]:
    """The bytes WeChat will accept: jpg/png, under 1 MB, sane dimensions.

    ``media/uploadimg`` refuses anything bigger, and the club's photos come straight off
    a phone. Pillow is used when available; without it an oversized file is reported
    rather than silently rejected by WeChat.
    """
    path = Path(path)
    raw = path.read_bytes()

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow ships with the runtime
        if len(raw) <= IMAGE_MAX_BYTES:
            return raw, path.name
        raise WeChatError(
            f"{path.name} is {len(raw) / 1024 / 1024:.1f} MB and WeChat's limit is 1 MB, "
            "and Pillow is not installed to resize it."
        )

    try:
        with Image.open(path) as probe:
            size = probe.size
    except Exception as exc:
        # A renamed or truncated file would otherwise surface as a PIL traceback in the
        # middle of a send, after some photos are already in the club's account.
        raise WeChatError(
            f"{path.name} is not an image WeChat can read ({type(exc).__name__}); "
            "media/uploadimg accepts jpg and png only."
        ) from exc

    if len(raw) <= IMAGE_MAX_BYTES and max(size) <= IMAGE_MAX_PX:
        return raw, path.name

    with Image.open(path) as image:
        image = _flatten(image)
        if max(image.size) > IMAGE_MAX_PX:
            scale = IMAGE_MAX_PX / max(image.size)
            image = image.resize((max(1, int(image.width * scale)),
                                  max(1, int(image.height * scale))), Image.LANCZOS)
        for quality in (88, 80, 70, 60):
            buffer = _encode_jpeg(image, quality)
            if len(buffer) <= IMAGE_MAX_BYTES:
                return buffer, f"{path.stem}.jpg"
        # Last resort: shrink rather than fail; the photo is for a phone screen.
        smaller = image.resize((max(1, image.width // 2), max(1, image.height // 2)),
                               Image.LANCZOS)
        for retry in (80, 70, 60):
            buffer = _encode_jpeg(smaller, retry)
            if len(buffer) <= IMAGE_MAX_BYTES:
                return buffer, f"{path.stem}.jpg"
    raise WeChatError(f"could not bring {path.name} under WeChat's 1 MB image limit")


def _flatten(image):
    """RGB, with any transparency composited onto white rather than turned black."""
    from PIL import Image

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def _encode_jpeg(image, quality: int) -> bytes:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


# --------------------------------------------------------------------- draft payload
def build_draft_payload(article: dict, content_html: str, thumb_media_id: str = "",
                        comment: bool = False) -> dict:
    """The exact JSON ``draft/add`` takes, with WeChat's own length limits applied."""
    title = str((article.get("title") or {}).get("cn") or "").strip()
    if len(title) > TITLE_MAX:
        title = title[:TITLE_MAX]
    lead = str((article.get("lead") or {}).get("cn") or "").strip()
    digest = lead[:DIGEST_CHARS] if lead else ""
    if len(digest) > DIGEST_MAX:
        digest = digest[:DIGEST_MAX]
    credits = article.get("credits") or {}
    author = str(credits.get("文字") or "").strip()[:AUTHOR_MAX]
    toc = article.get("toc") or {}
    source_url = str(toc.get("previous_url") or "").strip()

    entry: dict[str, Any] = {
        "article_type": "news",
        "title": title,
        "digest": digest,
        "content": content_html,
        "need_open_comment": 1 if comment else 0,
        "only_fans_can_comment": 0,
    }
    if author:
        entry["author"] = author
    if thumb_media_id:
        entry["thumb_media_id"] = thumb_media_id
    if source_url:
        entry["content_source_url"] = source_url
    return {"articles": [entry]}


def content_size_warning(payload: dict) -> str:
    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if size > CONTENT_MAX_BYTES:
        return (f"the draft payload is {size / 1024:.0f} KB; WeChat refuses anything over "
                "1 MB. Shorten the article or split it.")
    return ""


def public_ip(timeout: int = 6) -> str:
    """Best-effort: the address the 公众号 IP 白名单 has to contain.

    WeChat rejects every call from an unlisted address with ``errcode 40164``, and the
    hardest part of the setup is finding out which address that is. This is a courtesy
    lookup through two public echo services; failing is normal and never fatal.
    """
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                text = response.read().decode("utf-8", "replace").strip()
            if text and len(text) <= 45:
                return text
        except Exception:
            continue
    return ""


def check_credentials(settings: WeChatSettings | None = None, transport: Any | None = None,
                      probe_ip: bool = True) -> dict:
    """Ask WeChat for an access_token — the one call that proves the setup works.

    Everything else in the draft route fails in ways that look alike; this separates them:
    bad AppID (40013), bad AppSecret (40125), a missing IP whitelist entry (40164), and an
    account without the interface permission (48001) each come back with the fix.
    """
    settings = settings or WeChatSettings.load()
    result: dict[str, Any] = {
        "ok": False, "appid": settings.appid, "error": "", "token": "", "public_ip": "",
    }
    if not settings.configured:
        result["error"] = (
            "No 公众号 credentials yet. Set HSIYC_WECHAT_APPID and HSIYC_WECHAT_SECRET "
            "(公众号后台 → 设置与开发 → 基本配置)."
        )
        if probe_ip:
            result["public_ip"] = public_ip()
        return result
    if probe_ip:
        result["public_ip"] = public_ip()
    try:
        token = WeChatClient(settings, transport).token()
    except WeChatError as exc:
        result["error"] = str(exc)
        return result
    except Exception as exc:  # a DNS failure, a proxy, no network at all
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    result["ok"] = True
    result["token"] = f"{token[:10]}… ({len(token)} characters)"
    return result


# ------------------------------------------------------------------------ bundle flow
@dataclass
class DraftResult:
    payload: dict = field(default_factory=dict)
    draft_media_id: str = ""
    uploaded: list[tuple[str, str]] = field(default_factory=list)
    cover_media_id: str = ""
    notes: list[str] = field(default_factory=list)
    sent: bool = False

    def as_dict(self) -> dict:
        return {
            "sent": self.sent,
            "draft_media_id": self.draft_media_id,
            "cover_media_id": self.cover_media_id,
            "uploaded": [{"file": name, "url": url} for name, url in self.uploaded],
            "notes": self.notes,
            "payload": self.payload,
        }


def bundle_paths(bundle: Path) -> tuple[dict, Path | None]:
    """``(article, cover)`` for a bundle folder."""
    bundle = Path(bundle)
    if bundle.is_file():
        bundle = bundle.parent
    slug = bundle.name
    candidates = [bundle / f"{slug}.json", *sorted(bundle.glob("*.json"))]
    for candidate in candidates:
        if candidate.name in ("check_report.json", "wechat-draft.json"):
            continue
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and data.get("sections"):
            cover = bundle / "art" / "cover.png"
            if not cover.is_file():
                covers = sorted((bundle / "art").glob("cover*"))
                cover = covers[0] if covers else None
            return data, cover
    raise WeChatError(f"no article JSON in {bundle}")


def photo_paths(bundle: Path, article: dict) -> list[tuple[str, Path]]:
    """Every placed photo, in reading order, resolved inside the bundle."""
    bundle = Path(bundle)
    media = bundle / "media"
    found: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for section in article.get("sections") or []:
        for block in section.get("body") or []:
            if block.get("kind") != "photo_grid":
                continue
            for photo in block.get("photos") or []:
                name = str(photo.get("file") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                candidate = media / Path(name).name
                if not candidate.is_file():
                    matches = [p for p in bundle.rglob(Path(name).name) if p.is_file()]
                    candidate = matches[0] if matches else candidate
                found.append((name, candidate))
    return found


def create_draft(
    bundle: Path,
    settings: WeChatSettings | None = None,
    *,
    send: bool = False,
    transport: Any | None = None,
    progress: Callable[[str], None] | None = None,
) -> DraftResult:
    """Build the draft for one bundle, and - only with ``send=True`` - create it.

    Dry run is the default everywhere: a draft is external state in the club's account,
    and pressing a button must not create one by accident. The payload is written into
    the bundle either way, so what *would* be sent is always inspectable.
    """
    from .render import to_xiumi_html

    bundle = Path(bundle)
    article, cover = bundle_paths(bundle)
    settings = settings or WeChatSettings.load()
    result = DraftResult()
    say = progress or (lambda message: None)

    photos = photo_paths(bundle, article)
    missing = [name for name, path in photos if not path.is_file()]
    if send and missing:
        raise WeChatError(
            "these photos are placed in the article but not in the bundle: "
            + ", ".join(missing)
        )

    images: dict[str, str] = {}
    if send:
        client = WeChatClient(settings, transport)
        say(f"uploading {len(photos)} photo(s) to WeChat")
        for name, path in photos:
            url = client.upload_content_image(path)
            images[name] = url
            result.uploaded.append((name, url))
        if cover and cover.is_file():
            result.cover_media_id = client.upload_cover(cover)
        else:
            say("no cover in art/ — WeChat requires a cover for a news draft")
    else:
        say(f"dry run: {len(photos)} photo(s) would be uploaded, plus the cover")

    content = to_xiumi_html(article, images=images)
    payload = build_draft_payload(article, content, result.cover_media_id)
    result.payload = payload
    if not send:
        payload = {  # keep the dry-run copy readable: no half-built image URLs
            "articles": [{**payload["articles"][0], "content": content}],
        }
        result.payload = payload

    warning = content_size_warning(result.payload)
    if warning:
        result.notes.append(warning)
        say(warning)
    entry = result.payload["articles"][0]
    say(f"title {len(entry['title'])}/{TITLE_MAX} chars, digest {len(entry.get('digest', ''))} chars, "
        f"content {len(entry['content']):,} chars")

    if send:
        client = client if send else None
        result.draft_media_id = client.add_draft(result.payload)  # type: ignore[union-attr]
        result.sent = True
        say(f"draft created: media_id {result.draft_media_id}")
    else:
        result.notes.append("dry run — nothing was sent to WeChat; pass --send to create the draft")

    (bundle / "wechat-draft.json").write_text(
        json.dumps(result.as_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return result
