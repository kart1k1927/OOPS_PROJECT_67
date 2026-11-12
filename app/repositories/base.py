"""Repository pattern: the abstract side.

Services depend on these interfaces, never on Supabase. Two implementations
exist: SupabaseIncidentRepository for the running application and
InMemoryIncidentRepository for the tests, which is the practical payoff. The
test suite exercises the real domain logic with no network, no keys and no
fixtures to reset, because the service cannot tell the difference.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from app.domain.enums import Priority, Role, SLAState, Status

T = TypeVar("T")


@dataclass(slots=True)
class IncidentQuery:
    """The search and filter criteria. The brief asks for at least five; this
    carries nine, and they compose."""

    text: str | None = None
    reference: str | None = None
    status: list[Status] = field(default_factory=list)
    priority: list[Priority] = field(default_factory=list)
    category_id: UUID | None = None
    service_id: UUID | None = None
    technician_id: UUID | None = None
    reporter_id: UUID | None = None
    sla_state: SLAState | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    open_only: bool = False
    unassigned_only: bool = False
    sort: str = "priority"  # priority | created | updated | sla
    limit: int = 100
    offset: int = 0

    def is_filtered(self) -> bool:
        return any(
            [
                self.text,
                self.reference,
                self.status,
                self.priority,
                self.category_id,
                self.service_id,
                self.technician_id,
                self.sla_state,
                self.created_from,
                self.created_to,
                self.open_only,
                self.unassigned_only,
            ]
        )

    def active_filters(self) -> list[tuple[str, str]]:
        """Rendered as removable chips under the filter bar."""
        chips: list[tuple[str, str]] = []
        if self.text:
            chips.append(("text", f'"{self.text}"'))
        for s in self.status:
            chips.append(("status", s.label))
        for p in self.priority:
            chips.append(("priority", f"{p.value} {p.label}"))
        if self.sla_state:
            chips.append(("sla_state", f"SLA {self.sla_state.label}"))
        if self.unassigned_only:
            chips.append(("unassigned_only", "Unassigned"))
        if self.open_only:
            chips.append(("open_only", "Open only"))
        return chips


class Repository(ABC, Generic[T]):
    @abstractmethod
    def get(self, entity_id: UUID) -> T | None: ...

    @abstractmethod
    def add(self, entity: T) -> T: ...

    @abstractmethod
    def update(self, entity: T) -> T: ...


class UserRepository(Repository):
    @abstractmethod
    def get_by_email(self, email: str): ...

    @abstractmethod
    def list_by_role(self, role: Role) -> list: ...

    @abstractmethod
    def list_all(self) -> list: ...

    @abstractmethod
    def list_technicians(self, *, with_workload: bool = True) -> list: ...

    @abstractmethod
    def set_skills(self, technician_id: UUID, category_ids: list[UUID]) -> None: ...


class CatalogRepository(ABC):
    @abstractmethod
    def list_services(self, *, active_only: bool = True) -> list: ...

    @abstractmethod
    def get_service(self, service_id: UUID): ...

    @abstractmethod
    def list_categories(self) -> list: ...

    @abstractmethod
    def get_category(self, category_id: UUID): ...

    @abstractmethod
    def list_sla_policies(self) -> list: ...

    @abstractmethod
    def get_sla_policy(self, priority: Priority): ...

    @abstractmethod
    def save_sla_policy(self, policy) -> None: ...

    @abstractmethod
    def add_service(self, service): ...

    @abstractmethod
    def add_category(self, category): ...


class IncidentRepository(Repository):
    @abstractmethod
    def search(self, query: IncidentQuery) -> list: ...

    @abstractmethod
    def count(self, query: IncidentQuery) -> int: ...

    @abstractmethod
    def add_update(self, update) -> None: ...

    @abstractmethod
    def list_updates(self, incident_id: UUID) -> list: ...

    @abstractmethod
    def active_workload(self) -> dict[UUID, int]: ...

    @abstractmethod
    def resolved_counts(self) -> dict[UUID, int]: ...

    @abstractmethod
    def recent_for_service(self, service_id: UUID | None, *, within_hours: int, exclude_id: UUID | None = None) -> list: ...

    @abstractmethod
    def open_incidents(self) -> list: ...

    @abstractmethod
    def resolved_with_notes(self, category_id: UUID | None, *, limit: int = 50) -> list: ...


class AuditRepository(ABC):
    @abstractmethod
    def record(self, *, actor_id: UUID | None, action: str, entity_type: str, entity_id: UUID | None, details: dict) -> None: ...

    @abstractmethod
    def recent(self, *, limit: int = 50) -> list[dict]: ...


class NotificationRepository(ABC):
    @abstractmethod
    def add(self, *, user_id: UUID, incident_id: UUID | None, title: str, message: str, channel: str, event_type: str | None) -> None: ...

    @abstractmethod
    def list_for_user(self, user_id: UUID, *, unread_only: bool = False, limit: int = 30) -> list[dict]: ...

    @abstractmethod
    def mark_read(self, notification_id: UUID, user_id: UUID) -> None: ...

    @abstractmethod
    def mark_all_read(self, user_id: UUID) -> None: ...

    @abstractmethod
    def unread_count(self, user_id: UUID) -> int: ...
