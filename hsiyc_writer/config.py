"""Configuration: API credentials, model routing and paths.

The API key is deliberately never hard-coded. It is resolved, in order, from:

1. the environment variable ``DEEPSEEK_API_KEY``
2. a local file ``.deepseek_key`` in the package directory (git-ignored)

Ask the agent to print the key anywhere and you get a masked form back.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
SPEC_DIR = PROJECT_DIR / "spec"
CORPUS_DIR = PROJECT_DIR / "spec" / "corpus"
OUTPUT_DIR = PROJECT_DIR / "output"
UPLOAD_DIR = PROJECT_DIR / "_work" / "uploads"

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_TEXT_MODEL = "deepseek-chat"
DEFAULT_VISION_MODEL = "deepseek-flash"
DEFAULT_REASONING_MODEL = "deepseek-v4-pro"


class ConfigError(RuntimeError):
    """Raised when the agent cannot be configured well enough to run."""


def mask(secret: str) -> str:
    """Return a display-safe version of a secret."""
    if not secret:
        return "(unset)"
    if len(secret) <= 10:
        return secret[:2] + "*" * (len(secret) - 2)
    return f"{secret[:6]}...{secret[-4:]} (len={len(secret)})"


def _read_key_file() -> str:
    for name in (".deepseek_key", "deepseek_key.txt"):
        path = PACKAGE_DIR / name
        if path.is_file():
            text = path.read_text(encoding="utf-8-sig").strip()
            # tolerate `DEEPSEEK_API_KEY=sk-...` style lines
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    line = line.split("=", 1)[1].strip().strip("'\"")
                if line:
                    return line
    return ""


@dataclass
class Settings:
    """Runtime settings for one agent run."""

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    text_model: str = DEFAULT_TEXT_MODEL
    vision_model: str = DEFAULT_VISION_MODEL
    reasoning_model: str = DEFAULT_REASONING_MODEL
    temperature: float = 0.7
    max_tokens: int = 16000
    timeout: int = 300
    max_retries: int = 3
    vision_enabled: bool = True
    max_photos: int = 12
    photo_max_px: int = 1400
    extras: dict = field(default_factory=dict)

    @classmethod
    def load(cls, require_key: bool = True) -> "Settings":
        s = cls(
            api_key=os.environ.get("DEEPSEEK_API_KEY", "").strip() or _read_key_file(),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            text_model=os.environ.get("HSIYC_TEXT_MODEL", DEFAULT_TEXT_MODEL),
            vision_model=os.environ.get("HSIYC_VISION_MODEL", DEFAULT_VISION_MODEL),
            reasoning_model=os.environ.get("HSIYC_REASONING_MODEL", DEFAULT_REASONING_MODEL),
        )
        if require_key and not s.api_key:
            raise ConfigError(
                "No DeepSeek API key found.\n"
                "Set it one of these ways:\n"
                "  * PowerShell:  $env:DEEPSEEK_API_KEY='sk-...'\n"
                "  * or write the key into: " + str(PACKAGE_DIR / ".deepseek_key")
            )
        return s

    @property
    def masked_key(self) -> str:
        return mask(self.api_key)


def ensure_dirs() -> None:
    for path in (OUTPUT_DIR, UPLOAD_DIR, SPEC_DIR):
        path.mkdir(parents=True, exist_ok=True)
