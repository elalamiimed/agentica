"""HTTP client for the agent's own API - lets a script drive the running web app.

Useful when the club wants to batch-generate articles while the UI server is up, or
to integrate the agent with another tool. Standard library only.

    from hsiyc_writer.apiclient import generate_via_api, develop_via_api
    result = generate_via_api("http://127.0.0.1:8765", brief_text, photos=[...])
    better = develop_via_api("http://127.0.0.1:8765", "32 students, 1v1 blitz, Tugsuu won")
"""

from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, Sequence


class ApiError(RuntimeError):
    pass


def _multipart(brief: str, doc_type: str, repair_rounds: int, photos: Sequence[Path]):
    boundary = "----HSIYC" + uuid.uuid4().hex
    body = bytearray()

    def field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))

    field("brief", brief)
    field("doc_type", doc_type)
    field("repair_rounds", str(repair_rounds))
    for photo in photos:
        path = Path(photo)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"photos\"; "
            f"filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8")
        )
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def develop_via_api(base_url: str, text: str, doc_type: str = "", timeout_s: int = 180) -> dict:
    """Improve a rough event description without generating an article.

    Returns ``{"description", "questions", "dropped", "unsourced", ...}`` - the same payload
    the page's "Develop this description" button shows. ``unsourced`` lists figures, dates
    and Latin names in the rewrite that were not in ``text``; when it is non-empty, read the
    rewrite before using it.
    """
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/develop",
        data=json.dumps({"text": text, "doc_type": doc_type}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise ApiError(f"POST /api/develop failed: HTTP {exc.code} {detail}") from exc


def generate_via_api(
    base_url: str,
    brief: str,
    *,
    photos: Sequence[Path] = (),
    doc_type: str = "",
    repair_rounds: int = 1,
    timeout_s: int = 900,
    poll_s: float = 2.0,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Submit a brief and block until the article is ready. Returns the job result."""
    base = base_url.rstrip("/")
    body, content_type = _multipart(brief, doc_type, repair_rounds, photos)
    request = urllib.request.Request(
        f"{base}/api/generate", data=body, headers={"Content-Type": content_type}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            job = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ApiError(f"POST /api/generate failed: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')[:300]}") from exc
    job_id = job.get("job_id")
    if not job_id:
        raise ApiError(f"unexpected response: {job}")

    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        time.sleep(poll_s)
        try:
            with urllib.request.urlopen(f"{base}/api/job/{job_id}", timeout=60) as response:
                state = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ApiError(f"GET /api/job failed: HTTP {exc.code}") from exc
        if progress and state.get("progress"):
            newest = state["progress"][-1]
            if newest != last:
                progress(newest)
                last = newest
        if state.get("status") == "done":
            return state
        if state.get("status") == "error":
            raise ApiError(state.get("error") or "generation failed")
    raise ApiError(f"timed out after {timeout_s}s waiting for job {job_id}")
