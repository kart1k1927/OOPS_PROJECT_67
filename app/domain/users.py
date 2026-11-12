"""User hierarchy.

Inheritance is used here because the "is-a" test genuinely passes: a Technician
is a User, an Administrator is a User. What differs between them is not data but
behaviour, which is the other half of the test. Each subclass answers the same
three questions differently:

    home_route()            where signing in takes them
    can_view(incident)      which incidents they are allowed to open
    available_actions(inc)  what they may do to this incident right now

The API and the templates call those three methods and never ask "if role ==".
Adding a Team Lead role means adding a class, not editing a chain of ifs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import UnauthorizedOperationError, ValidationError
from app.domain.actions import Action
from app.domain.enums import Role, Status


class User(ABC):
    def __init__(
        self,
        *,
        employee_code: str,
        full_name: str,
        email: str,
        id: UUID | None = None,
        is_active: bool = True,
        created_at: datetime | None = None,
        password_hash: str | None = None,
    ) -> None:
        self._id = id or uuid4()
        self._employee_code = employee_code
        self._full_name = self._validated_name(full_name)
        self._email = self._validated_email(email)
        self._is_active = is_active
        self._created_at = created_at or datetime.now(timezone.utc)
        self._password_hash = password_hash

    # --- validation ---------------------------------------------------------

    @staticmethod
    def _validated_name(name: str) -> str:
        cleaned = (name or "").strip()
        if len(cleaned) < 2:
            raise ValidationError("Enter your full name.", field="full_name")
        return cleaned

    @staticmethod
    def _validated_email(email: str) -> str:
        cleaned = (email or "").strip().lower()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1] or len(cleaned) < 6:
            raise ValidationError("Enter a valid email address.", field="email")
        return cleaned

    # --- readers --------------------------------------------------------------

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def employee_code(self) -> str:
        return self._employee_code

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def email(self) -> str:
        return self._email

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def password_hash(self) -> str | None:
        """Only the authentication service reads this. It is never serialised
        into an API response or a template context."""
        return self._password_hash

    @property
    def initials(self) -> str:
        parts = [p for p in self._full_name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    @abstractmethod
    def role(self) -> Role: ...

    # --- behaviour ------------------------------------------------------------

    def deactivate(self) -> None:
        self._is_active = False

    def activate(self) -> None:
        self._is_active = True

    def set_password_hash(self, value: str) -> None:
        self._password_hash = value

    @abstractmethod
    def home_route(self) -> str: ...

    @abstractmethod
    def can_view(self, incident) -> bool: ...

    @abstractmethod
    def available_actions(self, incident) -> list[Action]: ...

    def view_refusal(self, incident) -> str:
        return f"{incident.reference} is not yours to open."

    def require_can_view(self, incident) -> None:
        if not self.can_view(incident):
            raise UnauthorizedOperationError(self.view_refusal(incident))

    def require_action(self, incident, key: str) -> Action:
        """Authorisation and the state machine, checked together.

        Every write endpoint goes through here, so a crafted request cannot do
        what the UI does not offer."""
        for action in self.available_actions(incident):
            if action.key == key:
                return action
        raise UnauthorizedOperationError(
            f"You cannot {key.replace('_', ' ')} {incident.reference} while it is {incident.status.value}."
        )

    @property
    def can_manage_catalog(self) -> bool:
        return False

    @property
    def can_view_audit_log(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and other.id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._employee_code} {self._full_name}>"


class Employee(User):
    """Reports incidents and confirms the fix."""

    @property
    def role(self) -> Role:
        return Role.EMPLOYEE

    def home_route(self) -> str:
        return "/my-incidents"

    def can_view(self, incident) -> bool:
        return incident.reporter_id == self._id

    def view_refusal(self, incident) -> str:
        return f"{incident.reference} was reported by somebody else, so you cannot open it."

    def available_actions(self, incident) -> list[Action]:
        if not self.can_view(incident):
            return []
        actions: list[Action] = []
        if incident.status is Status.RESOLVED:
            actions.append(Action("verify", "Confirm the fix", Status.VERIFIED, style="primary"))
            actions.append(Action("reopen", "It is still broken", Status.IN_PROGRESS, needs_note=True, style="danger"))
        if incident.status is Status.VERIFIED:
            actions.append(Action("close", "Close incident", Status.CLOSED, style="primary"))
        if incident.status is not Status.CLOSED:
            actions.append(Action("add_note", "Add information", needs_note=True))
        if incident.status in (Status.RESOLVED, Status.VERIFIED, Status.CLOSED) and incident.feedback_rating is None:
            actions.append(Action("feedback", "Rate the resolution"))
        return actions


class Technician(User):
    """Works the queue. Composition: has-a set of skills and a workload."""

    def __init__(
        self,
        *,
        skills: set[UUID] | None = None,
        max_workload: int = 5,
        experience_level: int = 1,
        active_workload: int = 0,
        resolved_count: int = 0,
        skill_names: tuple[str, ...] = (),
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._skills = set(skills or ())
        self._max_workload = max(1, int(max_workload))
        self._experience_level = min(5, max(1, int(experience_level)))
        self._active_workload = int(active_workload)
        self._resolved_count = int(resolved_count)
        self._skill_names = tuple(skill_names)

    @property
    def role(self) -> Role:
        return Role.TECHNICIAN

    @property
    def skills(self) -> frozenset[UUID]:
        return frozenset(self._skills)

    @property
    def skill_names(self) -> tuple[str, ...]:
        return self._skill_names

    @property
    def max_workload(self) -> int:
        return self._max_workload

    @property
    def experience_level(self) -> int:
        return self._experience_level

    @property
    def active_workload(self) -> int:
        return self._active_workload

    @property
    def resolved_count(self) -> int:
        return self._resolved_count

    @property
    def has_capacity(self) -> bool:
        return self._active_workload < self._max_workload

    @property
    def spare_capacity(self) -> int:
        return self._max_workload - self._active_workload

    @property
    def load_fraction(self) -> float:
        return self._active_workload / self._max_workload if self._max_workload else 1.0

    def set_active_workload(self, count: int) -> None:
        self._active_workload = max(0, int(count))

    def set_resolved_count(self, count: int) -> None:
        self._resolved_count = max(0, int(count))

    def knows(self, category_id: UUID | None) -> bool:
        return category_id is not None and category_id in self._skills

    def is_available_for(self, incident) -> bool:
        return self._is_active and self.has_capacity

    def home_route(self) -> str:
        return "/queue"

    def can_view(self, incident) -> bool:
        # Their own work, plus anything unassigned so the queue can be picked up.
        return incident.assigned_technician_id in (self._id, None)

    def view_refusal(self, incident) -> str:
        return f"{incident.reference} is assigned to another technician."

    def available_actions(self, incident) -> list[Action]:
        if incident.assigned_technician_id != self._id:
            return []
        actions: list[Action] = []
        match incident.status:
            case Status.ASSIGNED:
                actions.append(Action("acknowledge", "Acknowledge", Status.ACKNOWLEDGED, style="primary"))
            case Status.ACKNOWLEDGED:
                actions.append(Action("start_work", "Start investigating", Status.IN_PROGRESS, style="primary"))
                actions.append(Action("hold", "Need information from reporter", Status.PENDING, needs_note=True))
            case Status.IN_PROGRESS:
                actions.append(Action("resolve", "Resolve incident", Status.RESOLVED, needs_note=True, style="primary"))
                actions.append(Action("hold", "Need information from reporter", Status.PENDING, needs_note=True))
            case Status.PENDING:
                actions.append(Action("resume", "Resume investigation", Status.IN_PROGRESS, style="primary"))
        if incident.status is not Status.CLOSED:
            actions.append(Action("add_note", "Add investigation note", needs_note=True))
        return actions


class Administrator(User):
    """Oversight. Sees everything, configures everything, resolves nothing."""

    @property
    def role(self) -> Role:
        return Role.ADMIN

    def home_route(self) -> str:
        return "/operations"

    def can_view(self, incident) -> bool:
        return True

    @property
    def can_manage_catalog(self) -> bool:
        return True

    @property
    def can_view_audit_log(self) -> bool:
        return True

    def available_actions(self, incident) -> list[Action]:
        actions: list[Action] = []
        if incident.is_open:
            label = "Reassign technician" if incident.is_assigned else "Assign technician"
            actions.append(Action("assign", label, style="primary" if not incident.is_assigned else "secondary"))
            actions.append(Action("escalate", "Escalate", needs_note=True))
            actions.append(Action("change_priority", "Change priority"))
        if incident.status is Status.VERIFIED:
            actions.append(Action("close", "Close incident", Status.CLOSED, style="primary"))
        if incident.status is not Status.CLOSED:
            actions.append(Action("add_note", "Add note", needs_note=True))
        return actions
