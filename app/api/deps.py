"""FastAPI dependencies.

The container is built once. get_current_user reads the session cookie, loads
the User, and hands back the correct subclass, so every endpoint below receives
an object that already knows what its role may do.
"""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from fastapi import Depends, Request

from app.core.exceptions import AuthenticationError, InactiveAccountError, UnauthorizedOperationError
from app.core.security import SESSION_COOKIE, read_token
from app.domain.enums import Role
from app.services.container import Container, build_container


_override: Container | None = None


def set_container(container: Container | None) -> None:
    """Testing seam. The HTTP tests point the whole application at the
    in-memory container, so they exercise the real routes, templates and
    authorisation without a database."""
    global _override
    _override = container
    _build_production_container.cache_clear()


@lru_cache(maxsize=1)
def _build_production_container() -> Container:
    return build_container()


def get_container() -> Container:
    return _override if _override is not None else _build_production_container()


def get_optional_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        claims = read_token(token)
        user = get_container().users.get(UUID(claims["sub"]))
    except Exception:
        return None
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AuthenticationError("Sign in to continue.")
    claims = read_token(token)
    user = get_container().users.get(UUID(claims["sub"]))
    if user is None:
        raise AuthenticationError("That account no longer exists.")
    if not user.is_active:
        raise InactiveAccountError()
    return user


def require_role(*roles: Role):
    """Role gate for a whole endpoint. Per incident authorisation still runs
    inside the service through User.require_action."""
    allowed = {Role(r) for r in roles}

    def dependency(user=Depends(get_current_user)):
        if user.role not in allowed:
            wanted = " or ".join(sorted(r.label for r in allowed))
            raise UnauthorizedOperationError(f"This page is for {wanted} accounts.")
        return user

    return dependency


require_admin = require_role(Role.ADMIN)
require_technician = require_role(Role.TECHNICIAN)
require_employee = require_role(Role.EMPLOYEE)
