"""Repository pattern: the in-memory side.

This is the reason the pattern is worth its weight. The test suite builds a
service with these, and gets the real domain logic with no network, no keys and
no database to reset between cases. IncidentService cannot tell the difference,
which is also the proof that it depends on the abstraction rather than on
Supabase.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.domain.catalog import Category, ITService, SLAPolicy
from app.domain.enums import Priority, Role, SLAState, Status
from app.domain.incident import Incident, IncidentUpdate
from app.repositories.base import (
    AuditRepository,
    CatalogRepository,
    IncidentQuery,
    IncidentRepository,
    NotificationRepository,
    UserRepository,
)

ACTIVE = {s for s in Status if s.is_open}


class InMemoryCatalogRepository(CatalogRepository):
    def __init__(self, *, services=(), categories=(), policies=()) -> None:
        self._services = {s.id: s for s in services}
        self._categories = {c.id: c for c in categories}
        self._policies = {p.priority: p for p in policies}

    def list_services(self, *, active_only: bool = True):
        return [s for s in self._services.values() if s.is_active or not active_only]

    def get_service(self, service_id):
        return self._services.get(service_id)

    def services_by_id(self):
        return dict(self._services)

    def list_categories(self):
        return list(self._categories.values())

    def get_category(self, category_id):
        return self._categories.get(category_id)

    def categories_by_id(self):
        return dict(self._categories)

    def list_sla_policies(self):
        return list(self._policies.values())

    def get_sla_policy(self, priority):
        return self._policies.get(Priority(priority))

    def policies_by_priority(self):
        return dict(self._policies)

    def save_sla_policy(self, policy):
        self._policies[policy.priority] = policy

    def add_service(self, service):
        self._services[service.id] = service
        return service

    def add_category(self, category):
        self._categories[category.id] = category
        return category

    def set_service_active(self, service_id, active):
        existing = self._services[service_id]
        self._services[service_id] = ITService(
            id=existing.id,
            name=existing.name,
            business_criticality=existing.business_criticality,
            description=existing.description,
            is_active=active,
        )


class InMemoryUserRepository(UserRepository):
    def __init__(self, users=(), incident_repo=None) -> None:
        self._users = {u.id: u for u in users}
        self._incidents = incident_repo

    def bind_incidents(self, incident_repo):
        self._incidents = incident_repo

    def _sync_workload(self, user):
        if self._incidents is not None and hasattr(user, "set_active_workload"):
            user.set_active_workload(self._incidents.active_workload().get(user.id, 0))
            user.set_resolved_count(self._incidents.resolved_counts().get(user.id, 0))
        return user

    def get(self, entity_id):
        user = self._users.get(entity_id)
        return self._sync_workload(user) if user else None

    def get_by_email(self, email):
        cleaned = (email or "").strip().lower()
        for user in self._users.values():
            if user.email == cleaned:
                return self._sync_workload(user)
        return None

    def get_by_code(self, employee_code):
        for user in self._users.values():
            if user.employee_code == employee_code:
                return self._sync_workload(user)
        return None

    def list_all(self):
        return [self._sync_workload(u) for u in sorted(self._users.values(), key=lambda u: u.employee_code)]

    def list_by_role(self, role):
        return [u for u in self.list_all() if u.role is Role(role)]

    def list_technicians(self, *, with_workload: bool = True):
        return self.list_by_role(Role.TECHNICIAN)

    def add(self, user):
        self._users[user.id] = user
        return user

    def update(self, user):
        self._users[user.id] = user
        return user

    def set_active(self, user_id, active):
        user = self._users[user_id]
        user.activate() if active else user.deactivate()

    def set_role(self, user_id, role):
        raise NotImplementedError("Role changes are not exercised by the in-memory repository.")

    def set_skills(self, technician_id, category_ids):
        raise NotImplementedError("Skills are set at construction in tests.")


class InMemoryIncidentRepository(IncidentRepository):
    def __init__(self) -> None:
        self._incidents: dict[UUID, Incident] = {}
        self._updates: list[IncidentUpdate] = []

    def get(self, entity_id, *, with_updates: bool = False):
        return self._incidents.get(entity_id)

    def add(self, incident):
        self._incidents[incident.id] = incident
        self._updates.extend(incident.updates)
        return incident

    def update(self, incident):
        self._incidents[incident.id] = incident
        return incident

    def add_update(self, update):
        self._updates.append(update)

    def list_updates(self, incident_id):
        return [u for u in self._updates if u.incident_id == incident_id]

    def _matches(self, incident: Incident, q: IncidentQuery) -> bool:
        if q.status and incident.status not in q.status:
            return False
        if q.open_only and not incident.is_open:
            return False
        if q.priority and incident.priority not in q.priority:
            return False
        if q.category_id and (incident.category is None or incident.category.id != q.category_id):
            return False
        if q.service_id and (incident.service is None or incident.service.id != q.service_id):
            return False
        if q.technician_id and incident.assigned_technician_id != q.technician_id:
            return False
        if q.unassigned_only and incident.assigned_technician_id is not None:
            return False
        if q.reporter_id and incident.reporter_id != q.reporter_id:
            return False
        if q.created_from and incident.created_at < q.created_from:
            return False
        if q.created_to and incident.created_at > q.created_to:
            return False
        if q.reference and not incident.reference.upper().startswith(q.reference.upper().removeprefix("INC-")[:6] and q.reference.upper()[:10]):
            if q.reference.upper().removeprefix("INC-") not in incident.reference.upper():
                return False
        if q.text:
            needle = q.text.lower()
            if needle not in incident.title.lower() and needle not in (incident.description or "").lower():
                return False
        if q.sla_state and incident.sla_state is not q.sla_state:
            return False
        return True

    def search(self, query: IncidentQuery):
        found = [i for i in self._incidents.values() if self._matches(i, query)]
        keys = {
            "priority": lambda i: (i.priority.rank, i.created_at),
            "created": lambda i: i.created_at,
            "updated": lambda i: i.updated_at,
            "sla": lambda i: i.sla.resolution_deadline_at or i.created_at,
        }
        found.sort(key=keys.get(query.sort, keys["created"]), reverse=query.sort in ("created", "updated"))
        return found[query.offset : query.offset + query.limit]

    def count(self, query: IncidentQuery) -> int:
        return len([i for i in self._incidents.values() if self._matches(i, query)])

    def active_workload(self):
        tally: dict[UUID, int] = {}
        for i in self._incidents.values():
            if i.is_open and i.assigned_technician_id:
                tally[i.assigned_technician_id] = tally.get(i.assigned_technician_id, 0) + 1
        return tally

    def resolved_counts(self):
        tally: dict[UUID, int] = {}
        for i in self._incidents.values():
            if i.status in (Status.RESOLVED, Status.VERIFIED, Status.CLOSED) and i.assigned_technician_id:
                tally[i.assigned_technician_id] = tally.get(i.assigned_technician_id, 0) + 1
        return tally

    def recent_for_service(self, service_id, *, within_hours: int = 48, exclude_id=None):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        return [
            i
            for i in self._incidents.values()
            if i.created_at >= cutoff
            and i.id != exclude_id
            and (service_id is None or (i.service and i.service.id == service_id))
        ]

    def open_incidents(self):
        return [i for i in self._incidents.values() if i.is_open]

    def resolved_with_notes(self, category_id, *, limit: int = 50):
        out = [
            i
            for i in self._incidents.values()
            if i.resolution_notes and (category_id is None or (i.category and i.category.id == category_id))
        ]
        return out[:limit]

    def status_tally(self):
        tally: dict[str, int] = {}
        for i in self._incidents.values():
            tally[i.status.value] = tally.get(i.status.value, 0) + 1
        return tally

    def service_tally(self):
        out: dict[str, dict] = {}
        for i in self._incidents.values():
            key = i.service.name if i.service else "Unassigned service"
            entry = out.setdefault(key, {"total": 0, "open": 0, "criticality": i.business_criticality})
            entry["total"] += 1
            if i.is_open:
                entry["open"] += 1
        return out

    def category_tally(self):
        out: dict[str, int] = {}
        for i in self._incidents.values():
            name = i.category.name if i.category else "Uncategorised"
            out[name] = out.get(name, 0) + 1
        return out


class InMemoryAuditRepository(AuditRepository):
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def record(self, *, actor_id, action, entity_type, entity_id, details):
        self.entries.append(
            {
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
                "created_at_dt": datetime.now(timezone.utc),
                "actor_name": details.get("actor_name", "System"),
            }
        )

    def recent(self, *, limit: int = 50):
        return list(reversed(self.entries))[:limit]


class InMemoryNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, *, user_id, incident_id, title, message, channel, event_type):
        self.items.append(
            {
                "id": uuid4(),
                "user_id": user_id,
                "incident_id": incident_id,
                "title": title,
                "message": message,
                "channel": channel,
                "event_type": event_type,
                "is_read": False,
                "created_at_dt": datetime.now(timezone.utc),
            }
        )

    def list_for_user(self, user_id, *, unread_only: bool = False, limit: int = 30):
        out = [n for n in reversed(self.items) if n["user_id"] == user_id and (not unread_only or not n["is_read"])]
        return out[:limit]

    def mark_read(self, notification_id, user_id):
        for n in self.items:
            if n["id"] == notification_id and n["user_id"] == user_id:
                n["is_read"] = True

    def mark_all_read(self, user_id):
        for n in self.items:
            if n["user_id"] == user_id:
                n["is_read"] = True

    def unread_count(self, user_id):
        return len([n for n in self.items if n["user_id"] == user_id and not n["is_read"]])
