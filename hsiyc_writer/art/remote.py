"""Optional online image generation.

DeepSeek - the club's only paid dependency - has no image endpoint; probing
``/images/generations`` returns 404 on every path. Text-to-image is therefore
delegated to a separate service and treated as strictly optional: if it is
unreachable, slow, rationed, or returns something that is not an image, the
caller falls back to the offline renderer and the bundle records which backend
actually produced each asset.

Two providers are supported:

* by default, the keyless public Pollinations endpoint. Measured on this
  machine it serves roughly one novel prompt in six - identical requests are
  cached and always succeed, but new prompts are rationed and answer HTTP 402
  once the budget is gone. That is a property of the free tier, not a bug here,
  so a 402 is treated as terminal and the artwork falls back immediately.
* optionally, any OpenAI-compatible ``POST /images/generations`` endpoint, set
  through ``HSIYC_ART_ENDPOINT`` + ``HSIYC_ART_API_KEY``. The club can point the
  agent at a provider it pays for without touching any code.

Every image is cached under ``_work/art_cache`` with the prompt, model, seed and
URL that produced it, so a submission can always be traced back to its source.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ..config import PROJECT_DIR

ENDPOINT = "https://image.pollinations.ai/prompt/{prompt}"
DEFAULT_MODEL = os.environ.get("HSIYC_ART_MODEL", "flux")
CACHE_DIR = PROJECT_DIR / "_work" / "art_cache"
USER_AGENT = "hsiyc-writer/1.0 (+local club article agent)"

# Kinds the service renders sensibly. A 6:1 divider band comes back as a mushy
# smear, so dividers are always drawn locally.
REMOTE_KINDS = ("banner", "poster", "social")

# 4xx codes that a retry cannot fix: quota, bad key, malformed request.
TERMINAL_STATUS = {400, 401, 402, 403, 404, 422}


class RemoteArtError(RuntimeError):
    """Raised when the online backend cannot deliver a usable image."""


class RemoteTerminalError(RemoteArtError):
    """A failure that retrying cannot fix (quota, bad key, bad request)."""


class RemoteQuotaError(RemoteTerminalError):
    """The provider is reachable but will not serve another image right now."""


# --------------------------------------------------------------------------- config
def custom_endpoint() -> tuple[str, str]:
    """An optional OpenAI-compatible images endpoint, for a paid key.

        HSIYC_ART_ENDPOINT=https://api.example.com/v1/images/generations
        HSIYC_ART_API_KEY=sk-...
        HSIYC_ART_MODEL=dall-e-3
    """
    return (os.environ.get("HSIYC_ART_ENDPOINT", "").strip(),
            os.environ.get("HSIYC_ART_API_KEY", "").strip())


def offline() -> bool:
    return os.environ.get("HSIYC_ART_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


def status(*, probe: bool = False, timeout: int = 10) -> dict:
    """Describe the backend, optionally with one cheap reachability check."""
    endpoint, key = custom_endpoint()
    info = {
        "enabled": not offline(),
        "endpoint": endpoint or ENDPOINT.format(prompt="..."),
        "provider": "custom (OpenAI-compatible)" if endpoint else "pollinations (keyless, rationed)",
        "model": os.environ.get("HSIYC_ART_MODEL", DEFAULT_MODEL),
        "keyed": bool(key),
        "reason": "disabled by HSIYC_ART_OFFLINE" if offline() else "enabled",
        "reachable": None,
    }
    if probe and not offline():
        if endpoint:
            info["reason"] = "custom endpoint configured; not probed"
            return info
        try:
            request = urllib.request.Request(
                ENDPOINT.format(prompt="test") + "?width=64&height=64&nologo=true&seed=1",
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                info["reachable"] = response.headers.get("Content-Type", "").startswith("image/")
                info["reason"] = "ok" if info["reachable"] else "unexpected content type"
        except urllib.error.HTTPError as exc:
            info["reachable"] = False
            info["reason"] = (f"HTTP {exc.code} - the free endpoint rations new images; set "
                              "HSIYC_ART_ENDPOINT + HSIYC_ART_API_KEY for a paid provider")
        except Exception as exc:  # reachability is informational, never fatal
            info["reachable"] = False
            info["reason"] = f"{type(exc).__name__}: {exc}"
    return info


def _cache_paths(prompt: str, width: int, height: int, model: str, seed: int) -> tuple[Path, Path]:
    endpoint, _key = custom_endpoint()
    size = os.environ.get("HSIYC_ART_SIZE", "") if endpoint else ""
    digest = hashlib.sha256(f"{endpoint or ENDPOINT}|{size}|{prompt}|{width}x{height}|{model}|{seed}".encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.png", CACHE_DIR / f"{digest}.json"


# --------------------------------------------------------------------------- providers
def _fetch_pollinations(prompt: str, width: int, height: int, model: str, seed: int,
                        timeout: int) -> tuple[bytes, str]:
    query = urllib.parse.urlencode({
        "width": int(width), "height": int(height), "model": model,
        "seed": seed, "nologo": "true", "enhance": "false",
    })
    url = ENDPOINT.format(prompt=urllib.parse.quote(prompt, safe="")) + "?" + query
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:120]
        if exc.code in (402, 429):
            raise RemoteQuotaError(
                f"HTTP {exc.code}: the keyless endpoint rations new images (cached prompts "
                f"still work). Set HSIYC_ART_ENDPOINT + HSIYC_ART_API_KEY for an unrationed "
                f"provider. {detail!r}") from exc
        if exc.code in TERMINAL_STATUS:
            raise RemoteTerminalError(f"HTTP {exc.code}: {detail!r}") from exc
        raise RemoteArtError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RemoteArtError(f"{type(exc.reason).__name__}: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise RemoteArtError(f"{type(exc).__name__}: {exc}") from exc
    if not content_type.startswith("image/"):
        raise RemoteArtError(f"unexpected content type {content_type!r}: {payload[:180]!r}")
    if len(payload) < 1024:
        raise RemoteArtError(f"suspiciously small image ({len(payload)} bytes)")
    return payload, url


def _fetch_custom(prompt: str, width: int, height: int, model: str, seed: int,
                  endpoint: str, key: str, timeout: int) -> tuple[bytes, str]:
    """OpenAI-compatible ``POST /images/generations``."""
    body = json.dumps({
        "model": model, "prompt": prompt, "n": 1,
        "size": os.environ.get("HSIYC_ART_SIZE", "").strip() or f"{int(width)}x{int(height)}",
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:200]
        if exc.code in (401, 403):
            raise RemoteTerminalError(f"HTTP {exc.code}: check HSIYC_ART_API_KEY. {detail!r}") from exc
        if exc.code in (402, 429):
            raise RemoteQuotaError(f"HTTP {exc.code}: provider refused (quota or rate limit). {detail!r}") from exc
        if exc.code in TERMINAL_STATUS:
            raise RemoteTerminalError(f"HTTP {exc.code}: {detail!r}") from exc
        raise RemoteArtError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RemoteArtError(f"{type(exc.reason).__name__}: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise RemoteArtError(f"{type(exc).__name__}: {exc}") from exc

    if content_type.startswith("image/"):
        return payload, endpoint
    try:
        data = json.loads(payload.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise RemoteArtError(f"provider returned neither an image nor JSON: {payload[:180]!r}") from exc
    entries = data.get("data") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        raise RemoteArtError(f"provider JSON had no data[]: {str(data)[:180]}")
    first = entries[0]
    if first.get("b64_json"):
        try:
            return base64.b64decode(first["b64_json"], validate=True), endpoint
        except (ValueError, TypeError, binascii.Error) as exc:
            raise RemoteArtError("provider returned invalid base64 image data") from exc
    if first.get("url"):
        if not isinstance(first["url"], str) or urllib.parse.urlparse(first["url"]).scheme not in {"http", "https"}:
            raise RemoteArtError("provider returned an invalid image URL")
        # Signed image URLs often point to a separate storage host. Never send
        # the generation API's bearer token to that host.
        headers = {"User-Agent": USER_AGENT}
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(first["url"], headers=headers), timeout=timeout) as response:
                return response.read(), first["url"]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise RemoteArtError(f"could not download generated image: {exc}") from exc
    raise RemoteArtError(f"provider entry had neither b64_json nor url: {str(first)[:180]}")


# --------------------------------------------------------------------------- entry point
def generate(prompt: str, width: int, height: int, *, model: str | None = None,
             seed: int | None = None, timeout: int = 150, retries: int = 2,
             cache: bool = True) -> dict:
    """Fetch one generated image. Raises :class:`RemoteArtError` on any failure.

    A fixed prompt always yields the same image: the seed is derived from the
    prompt unless one is given, and results are cached on disk, so re-running an
    article never spends the service's ration twice.
    """
    if offline():
        raise RemoteArtError("online image generation is disabled (HSIYC_ART_OFFLINE)")
    model = model or os.environ.get("HSIYC_ART_MODEL", DEFAULT_MODEL)
    endpoint, key = custom_endpoint()
    backend = "remote:custom" if endpoint else "remote:pollinations"
    if seed is None:
        seed = int(hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:6], 16)

    image_path, meta_path = _cache_paths(prompt, width, height, model, seed)
    if cache and image_path.is_file():
        try:
            with Image.open(image_path) as handle:
                image = handle.convert("RGB")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
            return {"image": image, "model": model, "seed": seed, "prompt": prompt,
                    "url": meta.get("url", ""), "cached": True, "backend": backend}
        except (OSError, UnidentifiedImageError, json.JSONDecodeError):
            image_path.unlink(missing_ok=True)  # a corrupt cache entry must not be fatal

    endpoint, key = custom_endpoint()
    last_error = ""
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(min(8.0, 1.5 * attempt))
        try:
            if endpoint:
                payload, url = _fetch_custom(prompt, width, height, model, seed, endpoint, key, timeout)
            else:
                payload, url = _fetch_pollinations(prompt, width, height, model, seed, timeout)
            image = Image.open(io.BytesIO(payload)).convert("RGB")
        except RemoteTerminalError:
            raise  # retrying a quota wall only makes the club wait
        except RemoteArtError as exc:
            last_error = str(exc)
            continue
        except (OSError, ValueError, Image.DecompressionBombError):
            last_error = "response was not a decodable image"
            continue
        else:
            if cache:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                temporary = image_path.with_suffix(".part")
                image.save(temporary, format="PNG")
                temporary.replace(image_path)  # atomic: no half-written cache entries
                meta_path.write_text(json.dumps({
                    "prompt": prompt, "model": model, "seed": seed, "url": url,
                    "width": width, "height": height,
                    "provider": endpoint or "pollinations",
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"image": image, "model": model, "seed": seed, "prompt": prompt,
                    "url": url, "cached": False, "backend": backend}

    raise RemoteArtError(f"{model} via {endpoint or ENDPOINT.format(prompt='')} "
                         f"failed after {retries + 1} attempt(s): {last_error}")
