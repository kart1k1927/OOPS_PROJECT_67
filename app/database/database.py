"""The Supabase client, created once.

Nothing outside app/repositories/ may import this module. That rule is what
makes the repository layer swappable: the in-memory repositories used by the
test suite never touch a network client, and no service or router knows which
implementation it is holding.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


def make_client() -> Client:
    """A fresh client with its own connection pool.

    The SLA monitor runs on a worker thread every 60 seconds and issues a burst
    of reads and writes. Sharing one pool with request handling meant both sides
    kept picking up connections the other had left idle, and Supabase drops
    idle HTTP/2 connections, so each side saw "Server disconnected" on calls
    that were never actually sent. Two pools, no contention.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache(maxsize=1)
def get_client() -> Client:
    """The shared client used to serve requests."""
    return make_client()


# Kept so that the original app.main health check keeps working.
def __getattr__(name: str):
    if name == "supabase":
        return get_client()
    raise AttributeError(name)
