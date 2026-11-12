"""Password hashing and session tokens.

PBKDF2-HMAC-SHA256 from the standard library rather than bcrypt or argon2, so
the project installs with pip and no compiler. 390,000 iterations matches the
current Django default. The stored format carries its own parameters, so the
iteration count can be raised later and old hashes still verify.

Passwords are never logged, never returned by an endpoint and never put in a
template context. The only thing that ever reads User.password_hash is
AuthService.authenticate.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ValidationError

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 390_000
JWT_ALGORITHM = "HS256"
SESSION_COOKIE = "itsm_session"

PASSWORD_MIN = 8


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii").strip()


def hash_password(password: str) -> str:
    validate_password_strength(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        return False
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_b64(digest), digest_b64)


def validate_password_strength(password: str) -> None:
    if len(password or "") < PASSWORD_MIN:
        raise ValidationError(
            f"Use at least {PASSWORD_MIN} characters for the password.", field="password"
        )
    if password.isdigit() or password.isalpha():
        raise ValidationError(
            "Mix letters and numbers in the password so it is not trivially guessable.", field="password"
        )


def issue_token(*, user_id: UUID, role: str, employee_code: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "code": employee_code,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.session_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def read_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Your session has expired. Sign in again.") from None
    except jwt.InvalidTokenError:
        raise AuthenticationError("That session is not valid. Sign in again.") from None
