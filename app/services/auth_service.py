"""Registration and sign in."""

from __future__ import annotations

import logging

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveAccountError,
    InvalidCredentialsError,
    ValidationError,
)
from app.core.security import hash_password, issue_token, verify_password
from app.domain.enums import Role
from app.domain.factories import UserFactory

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, user_repository, audit_repository=None) -> None:
        self._users = user_repository
        self._audit = audit_repository

    def _audit_quietly(self, **kwargs) -> None:
        """Record, but never fail the operation over it.

        Losing an audit line is bad. Refusing a sign in whose password was
        correct because the audit table was briefly unreachable is worse.
        """
        if self._audit is None:
            return
        try:
            self._audit.record(**kwargs)
        except Exception:
            logger.warning("Audit write failed for %s", kwargs.get("action"), exc_info=True)

    def register(self, *, full_name: str, email: str, password: str, role: Role = Role.EMPLOYEE):
        cleaned_email = (email or "").strip().lower()
        if self._users.get_by_email(cleaned_email) is not None:
            raise EmailAlreadyRegisteredError(cleaned_email)

        user = UserFactory.create(
            role,
            employee_code="PENDING",
            full_name=full_name,
            email=cleaned_email,
            password_hash=hash_password(password),
        )
        created = self._users.add(user)

        self._audit_quietly(
            actor_id=created.id,
            action="USER_REGISTERED",
            entity_type="user",
            entity_id=created.id,
            details={
                "description": f"{created.employee_code} ({created.full_name}) registered as {created.role.value}.",
                "actor_name": created.full_name,
            },
        )
        return created

    def authenticate(self, *, email: str, password: str):
        user = self._users.get_by_email((email or "").strip().lower())

        # Same message whether the address is unknown or the password is wrong,
        # so the form cannot be used to enumerate who has an account.
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        if not user.is_active:
            raise InactiveAccountError()

        self._audit_quietly(
            actor_id=user.id,
            action="USER_SIGNED_IN",
            entity_type="user",
            entity_id=user.id,
            details={"description": f"{user.employee_code} signed in.", "actor_name": user.full_name},
        )
        return user

    @staticmethod
    def token_for(user) -> str:
        return issue_token(user_id=user.id, role=user.role.value, employee_code=user.employee_code)

    def set_password(self, user, *, current: str, replacement: str) -> None:
        if not verify_password(current, user.password_hash):
            raise InvalidCredentialsError("The current password is not correct.")
        user.set_password_hash(hash_password(replacement))
        self._users.update(user)
