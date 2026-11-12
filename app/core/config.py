"""Configuration, read once at import and validated immediately.

A missing key fails at startup with a sentence that says which key and where to
put it, rather than at the first request with a TypeError from inside the
Supabase client.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = BASE_DIR / "app"

load_dotenv(BASE_DIR / ".env")


class ConfigurationError(RuntimeError):
    pass


def _required(key: str) -> str:
    value = (os.environ.get(key) or "").strip().strip('"')
    if not value:
        raise ConfigurationError(
            f"{key} is missing. Copy .env.example to .env and fill it in, then restart the server."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip().strip('"')


@dataclass(frozen=True, slots=True)
class Settings:
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str
    jwt_secret: str
    session_hours: int
    app_name: str = "I-ITSM"
    organisation: str = "BITS Pilani, Hyderabad Campus"

    @property
    def templates_dir(self) -> Path:
        return APP_DIR / "templates"

    @property
    def static_dir(self) -> Path:
        return APP_DIR / "static"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        supabase_url=_required("SUPABASE_URL"),
        # The backend is the only thing talking to Postgres, and it enforces
        # authorisation in Python (see User.require_action). The service key is
        # used deliberately so that row level security is not doing the
        # authorising; RLS stays enabled underneath as a second line.
        supabase_service_key=_required("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_anon_key=_optional("SUPABASE_ANON_KEY"),
        jwt_secret=_required("JWT_SECRET"),
        session_hours=int(_optional("SESSION_HOURS", "12") or 12),
    )
