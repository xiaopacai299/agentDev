"""Load runtime settings from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str | None
    model: str
    temperature: float


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    model = os.getenv("MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    temperature = float(os.getenv("TEMPERATURE", "0"))

    if not api_key:
        raise RuntimeError(
            "缺少 OPENAI_API_KEY。请复制 .env.example 为 .env，并填入密钥。"
        )

    return Settings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
    )
