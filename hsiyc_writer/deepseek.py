"""Minimal DeepSeek chat-completions client (standard library only).

Verified against the live endpoint:

* ``deepseek-chat`` is an alias that the service resolves to ``deepseek-flash``.
* ``response_format={"type": "json_object"}`` is supported (JSON mode).
* The message may carry ``reasoning_content``; it must be ignored when reading
  the answer.
* Vision input works on ``deepseek-flash`` via ``image_url`` content parts with a
  ``data:image/...;base64,...`` URL.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .config import Settings


class DeepSeekError(RuntimeError):
    """Any failure while talking to the DeepSeek API."""

    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class Reply:
    text: str
    reasoning: str = ""
    usage: Usage | None = None
    model: str = ""
    elapsed_s: float = 0.0


def image_part(path: str | Path, max_px: int = 1400) -> dict:
    """Build an ``image_url`` content part for a photo on disk.

    Photos are downscaled in memory when Pillow is available; the bytes on disk
    are never modified.
    """
    path = Path(path)
    if not path.is_file():
        raise DeepSeekError(f"Photo not found: {path}")
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    try:  # optional, keeps uploads small and cheap
        import io

        from PIL import Image

        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGB")
            if max(im.size) > max_px:
                scale = max_px / float(max(im.size))
                im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=82, optimize=True)
            raw = buf.getvalue()
            mime = "image/jpeg"
    except Exception:  # pragma: no cover - fall back to the original bytes
        pass
    b64 = base64.b64encode(raw).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


class DeepSeekClient:
    """Thin, dependency-free wrapper around ``POST /chat/completions``."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.usage = Usage()

    # ---------------------------------------------------------------- internals
    def _post(self, payload: dict) -> dict:
        url = f"{self.s.base_url}/chat/completions"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.s.api_key}",
                "Accept": "application/json",
            },
            method="POST",
        )
        last: Exception | None = None
        for attempt in range(1, self.s.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.s.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", "replace")
                except Exception:
                    pass
                # 4xx other than rate limiting will not fix themselves.
                if exc.code in (400, 401, 402, 403, 404, 422):
                    raise DeepSeekError(
                        f"DeepSeek API rejected the request (HTTP {exc.code}).", exc.code, body
                    ) from exc
                last = DeepSeekError(f"DeepSeek API HTTP {exc.code}", exc.code, body)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = DeepSeekError(f"DeepSeek API unreachable: {exc}")
            if attempt < self.s.max_retries:
                time.sleep(min(2 ** attempt, 10))
        raise last or DeepSeekError("DeepSeek API call failed")

    # ------------------------------------------------------------------- public
    def chat(
        self,
        messages: Sequence[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Reply:
        payload: dict[str, Any] = {
            "model": model or self.s.text_model,
            "messages": list(messages),
            "temperature": self.s.temperature if temperature is None else temperature,
            "max_tokens": self.s.max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.time()
        data = self._post(payload)
        elapsed = time.time() - started
        try:
            choice = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepSeekError(f"Unexpected API response shape: {str(data)[:400]}") from exc

        u = data.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(u.get("prompt_tokens") or 0),
            completion_tokens=int(u.get("completion_tokens") or 0),
            total_tokens=int(u.get("total_tokens") or 0),
            model=data.get("model", ""),
        )
        self.usage.add(usage)
        return Reply(
            text=(choice.get("content") or "").strip(),
            reasoning=(choice.get("reasoning_content") or "").strip(),
            usage=usage,
            model=data.get("model", ""),
            elapsed_s=elapsed,
        )

    def json_chat(
        self,
        messages: Sequence[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[dict, Reply]:
        """Chat in JSON mode and return ``(parsed_object, reply)``."""
        reply = self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        if not reply.text:
            raise DeepSeekError("Model returned an empty response where JSON was required.")
        return parse_json_loose(reply.text), reply

    def health(self) -> dict:
        """Cheap 'is the endpoint reachable' probe used by the web UI."""
        url = f"{self.s.base_url}/models"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.s.api_key}"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [m.get("id") for m in data.get("data", [])]
        return {"ok": True, "models": models}


def parse_json_loose(text: str) -> dict:
    """Parse JSON that may be wrapped in a ``` fence or surrounded by prose."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise DeepSeekError(f"Model did not return JSON. First 400 chars: {text[:400]}")
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise DeepSeekError(
                f"Model returned malformed JSON: {exc}. First 400 chars: {text[:400]}"
            ) from exc
    if not isinstance(value, dict):
        raise DeepSeekError(f"Expected a JSON object, got {type(value).__name__}")
    return value


def describe_usage(usages: Iterable[Usage]) -> str:
    total = Usage()
    for u in usages:
        total.add(u)
    return (
        f"{total.prompt_tokens} prompt + {total.completion_tokens} completion "
        f"= {total.total_tokens} tokens"
    )
