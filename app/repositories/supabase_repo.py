"""Repository pattern: the Supabase side.

Every method wraps its driver call so that no supabase or httpx exception
escapes this layer. Callers above see RepositoryError or a domain error, never
an APIError.
"""

from __future__ import annotations

import functools
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.exceptions import ITSMError, RepositoryError
from app.domain.catalog import Category, ITService, SLAPolicy, TechnicianSkill
from app.domain.enums import Priority, Role, SLAState, Status
from app.domain.incident import Incident, IncidentUpdate
from app.repositories import mappers as m
from app.repositories.base import (
    AuditRepository,
    CatalogRepository,
    IncidentQuery,
    IncidentRepository,
    NotificationRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = [s.value for s in Status if s.is_open]

REPORTER_JOIN = "reporter:profiles!incidents_reporter_id_fkey(id,full_name,employee_code)"
TECHNICIAN_JOIN = "technician:profiles!incidents_assigned_technician_id_fkey(id,full_name,employee_code)"
INCIDENT_SELECT = f"*,{REPORTER_JOIN},{TECHNICIAN_JOIN}"


# Supabase keeps HTTP/2 connections alive and sometimes drops an idle one. The
# next call then fails with "Server disconnected" before the request is even
# sent. That is not a real failure, it is a stale socket, and retrying on a
# fresh connection succeeds. Without this a dropped connection turns into a 503
# on whatever the user happened to be doing.
TRANSIENT = ("RemoteProtocolError", "ConnectError", "ConnectTimeout", "ReadTimeout", "ReadError", "PoolTimeout")
RETRIES = 3
BACKOFF_SECONDS = 0.4


def _is_transient(exc: Exception) -> bool:
    name = type(exc).__name__
    if name in TRANSIENT:
        return True
    cause = exc.__cause__
    return cause is not None and type(cause).__name__ in TRANSIENT


def guarded(fn):
    """Retry transient transport failures, then translate anything that is
    left into one application level error."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        last: Exception | None = None
        for attempt in range(1, RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except ITSMError:
                raise
            except Exception as exc:  # noqa: BLE001 - deliberate boundary
                last = exc
                if attempt < RETRIES and _is_transient(exc):
                    logger.warning(
                        "Storage call %s hit %s, retry %s of %s",
                        fn.__name__, type(exc).__name__, attempt, RETRIES - 1,
                    )
                    time.sleep(BACKOFF_SECONDS * attempt)
                    continue
                break

        logger.exception("Storage call %s failed", fn.__name__, exc_info=last)
        raise RepositoryError(
            f"The incident database rejected a {fn.__name__.replace('_', ' ')} request. {str(last)[:160]}"
        ) from last

    return wrapper


class SupabaseCatalogRepository(CatalogRepository):
    def __init__(self, client) -> None:
        self._db = client

    @guarded
    def list_services(self, *, active_only: bool = True) -> list[ITService]:
        q = self._db.table("services").select("*").order("name")
        if active_only:
            q = q.eq("is_active", True)
        return [m.to_service(r) for r in q.execute().data]

    def get_service(self, service_id: UUID) -> ITService | None:
        if service_id is None:
            return None
        return self.services_by_id().get(service_id)

    @guarded
    def services_by_id(self) -> dict[UUID, ITService]:
        return {s.id: s for s in (m.to_service(r) for r in self._db.table("services").select("*").execute().data)}

    @guarded
    def list_categories(self) -> list[Category]:
        return [m.to_category(r) for r in self._db.table("categories").select("*").order("name").execute().data]

    def get_category(self, category_id: UUID) -> Category | None:
        if category_id is None:
            return None
        return self.categories_by_id().get(category_id)

    @guarded
    def categories_by_id(self) -> dict[UUID, Category]:
        return {c.id: c for c in self.list_categories()}

    @guarded
    def list_sla_policies(self) -> list[SLAPolicy]:
        rows = self._db.table("sla_policies").select("*").order("priority").execute().data
        return [m.to_sla_policy(r) for r in rows]

    def get_sla_policy(self, priority: Priority) -> SLAPolicy | None:
        return self.policies_by_priority().get(Priority(priority))

    @guarded
    def policies_by_priority(self) -> dict[Priority, SLAPolicy]:
        return {p.priority: p for p in self.list_sla_policies()}

    @guarded
    def save_sla_policy(self, policy: SLAPolicy) -> None:
        self._db.table("sla_policies").update(
            {
                "response_hours": policy.response_hours,
                "resolution_hours": policy.resolution_hours,
                "escalation_hours": policy.escalation_hours,
            }
        ).eq("priority", policy.priority.value).execute()

    @guarded
    def add_service(self, service: ITService) -> ITService:
        row = self._db.table("services").insert(
            {
                "name": service.name,
                "description": service.description,
                "business_criticality": service.business_criticality,
                "is_active": service.is_active,
            }
        ).execute().data[0]
        return m.to_service(row)

    @guarded
    def add_category(self, category: Category) -> Category:
        row = self._db.table("categories").insert(
            {"name": category.name, "description": category.description}
        ).execute().data[0]
        return m.to_category(row)

    @guarded
    def set_service_active(self, service_id: UUID, active: bool) -> None:
        self._db.table("services").update({"is_active": active}).eq("id", str(service_id)).execute()


class SupabaseUserRepository(UserRepository):
    def __init__(self, client, incident_repo: "SupabaseIncidentRepository | None" = None) -> None:
        self._db = client
        self._incidents = incident_repo

    def bind_incidents(self, incident_repo) -> None:
        self._incidents = incident_repo

    @guarded
    def _skills_for(self, technician_ids: list[str]) -> tuple[dict, dict]:
        if not technician_ids:
            return {}, {}
        rows = (
            self._db.table("technician_skills")
            .select("technician_id,category_id,categories(name)")
            .in_("technician_id", technician_ids)
            .execute()
            .data
        )
        ids: dict = {}
        names: dict = {}
        for r in rows:
            tid = m.parse_uuid(r["technician_id"])
            ids.setdefault(tid, set()).add(m.parse_uuid(r["category_id"]))
            names.setdefault(tid, []).append((r.get("categories") or {}).get("name", ""))
        return ids, {k: tuple(sorted(n for n in v if n)) for k, v in names.items()}

    @guarded
    def get(self, entity_id: UUID):
        rows = self._db.table("profiles").select("*").eq("id", str(entity_id)).limit(1).execute().data
        if not rows:
            return None
        return self._hydrate(rows)[0]

    @guarded
    def get_by_email(self, email: str):
        cleaned = (email or "").strip().lower()
        rows = self._db.table("profiles").select("*").ilike("email", cleaned).limit(1).execute().data
        if not rows:
            return None
        return self._hydrate(rows)[0]

    @guarded
    def get_by_code(self, employee_code: str):
        rows = self._db.table("profiles").select("*").eq("employee_code", employee_code).limit(1).execute().data
        return self._hydrate(rows)[0] if rows else None

    @guarded
    def list_all(self) -> list:
        rows = self._db.table("profiles").select("*").order("employee_code").execute().data
        return self._hydrate(rows)

    @guarded
    def list_by_role(self, role: Role) -> list:
        rows = self._db.table("profiles").select("*").eq("role", Role(role).value).order("employee_code").execute().data
        return self._hydrate(rows)

    def list_technicians(self, *, with_workload: bool = True) -> list:
        return self.list_by_role(Role.TECHNICIAN)

    def _hydrate(self, rows: list[dict]) -> list:
        tech_ids = [r["id"] for r in rows if r.get("role") == Role.TECHNICIAN.value]
        skills, skill_names = self._skills_for(tech_ids)
        workload = self._incidents.active_workload() if (self._incidents and tech_ids) else {}
        resolved = self._incidents.resolved_counts() if (self._incidents and tech_ids) else {}
        users = []
        for r in rows:
            uid = m.parse_uuid(r["id"])
            users.append(
                m.to_user(
                    r,
                    skills=skills.get(uid, set()),
                    skill_names=skill_names.get(uid, ()),
                    active_workload=workload.get(uid, 0),
                    resolved_count=resolved.get(uid, 0),
                )
            )
        return users

    @guarded
    def add(self, user):
        row = m.user_to_row(user)
        row.pop("employee_code", None)  # let the sequence allocate EMPnnn
        inserted = self._db.table("profiles").insert(row).execute().data[0]
        return m.to_user(inserted)

    @guarded
    def update(self, user):
        self._db.table("profiles").update(m.user_to_row(user)).eq("id", str(user.id)).execute()
        return user

    @guarded
    def set_active(self, user_id: UUID, active: bool) -> None:
        self._db.table("profiles").update({"is_active": active}).eq("id", str(user_id)).execute()

    @guarded
    def set_role(self, user_id: UUID, role: Role) -> None:
        self._db.table("profiles").update({"role": Role(role).value}).eq("id", str(user_id)).execute()

    @guarded
    def set_skills(self, technician_id: UUID, category_ids: list[UUID]) -> None:
        self._db.table("technician_skills").delete().eq("technician_id", str(technician_id)).execute()
        if category_ids:
            self._db.table("technician_skills").insert(
                [{"technician_id": str(technician_id), "category_id": str(c)} for c in category_ids]
            ).execute()


class SupabaseIncidentRepository(IncidentRepository):
    def __init__(self, client, catalog: SupabaseCatalogRepository) -> None:
        self._db = client
        self._catalog = catalog

    def _context(self) -> tuple[dict, dict, dict]:
        return self._catalog.services_by_id(), self._catalog.categories_by_id(), self._catalog.policies_by_priority()

    @guarded
    def get(self, entity_id: UUID, *, with_updates: bool = False) -> Incident | None:
        rows = self._db.table("incidents").select(INCIDENT_SELECT).eq("id", str(entity_id)).limit(1).execute().data
        if not rows:
            return None
        services, categories, policies = self._context()
        updates = self.list_updates(entity_id) if with_updates else []
        return m.to_incident(rows[0], services=services, categories=categories, policies=policies, updates=updates)

    @guarded
    def add(self, incident: Incident) -> Incident:
        self._db.table("incidents").insert(m.incident_to_row(incident)).execute()
        for update in incident.updates:
            self.add_update(update)
        return incident

    @guarded
    def update(self, incident: Incident) -> Incident:
        row = m.incident_to_row(incident)
        row.pop("id", None)
        row.pop("created_at", None)
        self._db.table("incidents").update(row).eq("id", str(incident.id)).execute()
        return incident

    @guarded
    def add_update(self, update: IncidentUpdate) -> None:
        self._db.table("incident_updates").insert(m.update_to_row(update)).execute()

    @guarded
    def list_updates(self, incident_id: UUID) -> list[IncidentUpdate]:
        rows = (
            self._db.table("incident_updates")
            .select("*,author:profiles(id,full_name,employee_code)")
            .eq("incident_id", str(incident_id))
            .order("created_at")
            .execute()
            .data
        )
        return [m.to_update(r) for r in rows]

    def _apply(self, builder, query: IncidentQuery):
        if query.status:
            builder = builder.in_("status", [s.value for s in query.status])
        if query.open_only:
            builder = builder.in_("status", ACTIVE_STATUSES)
        if query.priority:
            builder = builder.in_("priority", [p.value for p in query.priority])
        if query.category_id:
            builder = builder.eq("category_id", str(query.category_id))
        if query.service_id:
            builder = builder.eq("service_id", str(query.service_id))
        if query.technician_id:
            builder = builder.eq("assigned_technician_id", str(query.technician_id))
        if query.unassigned_only:
            builder = builder.is_("assigned_technician_id", "null")
        if query.reporter_id:
            builder = builder.eq("reporter_id", str(query.reporter_id))
        if query.created_from:
            builder = builder.gte("created_at", query.created_from.isoformat())
        if query.created_to:
            builder = builder.lte("created_at", query.created_to.isoformat())
        if query.text:
            needle = query.text.replace("%", "").replace(",", " ").strip()
            if needle:
                builder = builder.or_(f"title.ilike.%{needle}%,description.ilike.%{needle}%")
        if query.sla_state is SLAState.BREACHED:
            builder = builder.or_("resolution_breached.eq.true,response_breached.eq.true")
        return builder

    @guarded
    def search(self, query: IncidentQuery) -> list[Incident]:
        builder = self._apply(self._db.table("incidents").select(INCIDENT_SELECT), query)

        if query.reference:
            # INC-8F51D7 is the first six hex digits of the uuid, so match the prefix.
            stem = query.reference.upper().removeprefix("INC-").lower()
            if stem:
                builder = builder.ilike("id", f"{stem[:8]}%")

        order = {
            "priority": ("priority", False),
            "created": ("created_at", True),
            "updated": ("updated_at", True),
            "sla": ("resolution_deadline_at", False),
        }.get(query.sort, ("created_at", True))
        builder = builder.order(order[0], desc=order[1])
        if order[0] == "priority":
            builder = builder.order("created_at", desc=False)

        builder = builder.range(query.offset, query.offset + query.limit - 1)
        rows = builder.execute().data

        services, categories, policies = self._context()
        incidents = [m.to_incident(r, services=services, categories=categories, policies=policies) for r in rows]

        # AT_RISK depends on elapsed fraction, which is arithmetic over two
        # timestamps rather than a stored column, so it is applied here.
        if query.sla_state is SLAState.AT_RISK:
            incidents = [i for i in incidents if i.sla_state is SLAState.AT_RISK]
        elif query.sla_state is SLAState.ON_TRACK:
            incidents = [i for i in incidents if i.sla_state is SLAState.ON_TRACK]
        return incidents

    @guarded
    def count(self, query: IncidentQuery) -> int:
        builder = self._apply(self._db.table("incidents").select("id", count="exact", head=True), query)
        return builder.execute().count or 0

    @guarded
    def active_workload(self) -> dict[UUID, int]:
        rows = (
            self._db.table("incidents")
            .select("assigned_technician_id")
            .in_("status", ACTIVE_STATUSES)
            .not_.is_("assigned_technician_id", "null")
            .execute()
            .data
        )
        tally: dict[UUID, int] = {}
        for r in rows:
            tid = m.parse_uuid(r["assigned_technician_id"])
            tally[tid] = tally.get(tid, 0) + 1
        return tally

    @guarded
    def resolved_counts(self) -> dict[UUID, int]:
        rows = (
            self._db.table("incidents")
            .select("assigned_technician_id")
            .in_("status", [Status.RESOLVED.value, Status.VERIFIED.value, Status.CLOSED.value])
            .not_.is_("assigned_technician_id", "null")
            .execute()
            .data
        )
        tally: dict[UUID, int] = {}
        for r in rows:
            tid = m.parse_uuid(r["assigned_technician_id"])
            tally[tid] = tally.get(tid, 0) + 1
        return tally

    @guarded
    def recent_for_service(self, service_id: UUID | None, *, within_hours: int = 48, exclude_id: UUID | None = None) -> list[Incident]:
        since = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()
        builder = self._db.table("incidents").select(INCIDENT_SELECT).gte("created_at", since)
        if service_id:
            builder = builder.eq("service_id", str(service_id))
        rows = builder.order("created_at", desc=True).limit(80).execute().data
        services, categories, policies = self._context()
        out = []
        for r in rows:
            if exclude_id and str(r["id"]) == str(exclude_id):
                continue
            out.append(m.to_incident(r, services=services, categories=categories, policies=policies))
        return out

    @guarded
    def open_incidents(self) -> list[Incident]:
        rows = (
            self._db.table("incidents")
            .select(INCIDENT_SELECT)
            .in_("status", ACTIVE_STATUSES)
            .order("priority")
            .limit(500)
            .execute()
            .data
        )
        services, categories, policies = self._context()
        return [m.to_incident(r, services=services, categories=categories, policies=policies) for r in rows]

    @guarded
    def resolved_with_notes(self, category_id: UUID | None, *, limit: int = 50) -> list[Incident]:
        builder = (
            self._db.table("incidents")
            .select(INCIDENT_SELECT)
            .not_.is_("resolution_notes", "null")
            .in_("status", [Status.RESOLVED.value, Status.VERIFIED.value, Status.CLOSED.value])
        )
        if category_id:
            builder = builder.eq("category_id", str(category_id))
        rows = builder.order("resolved_at", desc=True).limit(limit).execute().data
        services, categories, policies = self._context()
        return [m.to_incident(r, services=services, categories=categories, policies=policies) for r in rows]

    @guarded
    def status_tally(self) -> dict[str, int]:
        rows = self._db.table("incidents").select("status").limit(5000).execute().data
        tally: dict[str, int] = {}
        for r in rows:
            tally[r["status"]] = tally.get(r["status"], 0) + 1
        return tally

    @guarded
    def service_tally(self) -> dict[str, dict]:
        rows = self._db.table("incidents").select("service_id,status").limit(5000).execute().data
        services = self._catalog.services_by_id()
        out: dict[str, dict] = {}
        for r in rows:
            sid = m.parse_uuid(r.get("service_id"))
            service = services.get(sid)
            key = service.name if service else "Unassigned service"
            entry = out.setdefault(key, {"total": 0, "open": 0, "criticality": service.business_criticality if service else 0})
            entry["total"] += 1
            if r["status"] in ACTIVE_STATUSES:
                entry["open"] += 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["total"]))

    @guarded
    def category_tally(self) -> dict[str, int]:
        rows = self._db.table("incidents").select("category_id").limit(5000).execute().data
        categories = self._catalog.categories_by_id()
        out: dict[str, int] = {}
        for r in rows:
            cid = m.parse_uuid(r.get("category_id"))
            name = categories[cid].name if cid in categories else "Uncategorised"
            out[name] = out.get(name, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))


class SupabaseAuditRepository(AuditRepository):
    def __init__(self, client) -> None:
        self._db = client

    @guarded
    def record(self, *, actor_id, action, entity_type, entity_id, details) -> None:
        self._db.table("audit_logs").insert(
            {
                "actor_id": str(actor_id) if actor_id else None,
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id else None,
                "details": details,
            }
        ).execute()

    @guarded
    def recent(self, *, limit: int = 50) -> list[dict]:
        rows = (
            self._db.table("audit_logs")
            .select("*,actor:profiles(full_name,employee_code)")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        for r in rows:
            r["created_at_dt"] = m.parse_dt(r.get("created_at"))
            r["actor_name"] = (r.get("actor") or {}).get("full_name") or "System"
        return rows


class SupabaseNotificationRepository(NotificationRepository):
    def __init__(self, client) -> None:
        self._db = client

    @guarded
    def add(self, *, user_id, incident_id, title, message, channel, event_type) -> None:
        self._db.table("notifications").insert(
            {
                "user_id": str(user_id),
                "incident_id": str(incident_id) if incident_id else None,
                "title": title,
                "message": message,
                "channel": channel,
                "event_type": event_type,
            }
        ).execute()

    @guarded
    def list_for_user(self, user_id, *, unread_only: bool = False, limit: int = 30) -> list[dict]:
        builder = self._db.table("notifications").select("*").eq("user_id", str(user_id))
        if unread_only:
            builder = builder.eq("is_read", False)
        rows = builder.order("created_at", desc=True).limit(limit).execute().data
        for r in rows:
            r["created_at_dt"] = m.parse_dt(r.get("created_at"))
        return rows

    @guarded
    def mark_read(self, notification_id, user_id) -> None:
        self._db.table("notifications").update({"is_read": True}).eq("id", str(notification_id)).eq(
            "user_id", str(user_id)
        ).execute()

    @guarded
    def mark_all_read(self, user_id) -> None:
        self._db.table("notifications").update({"is_read": True}).eq("user_id", str(user_id)).eq(
            "is_read", False
        ).execute()

    @guarded
    def unread_count(self, user_id) -> int:
        return (
            self._db.table("notifications")
            .select("id", count="exact", head=True)
            .eq("user_id", str(user_id))
            .eq("is_read", False)
            .execute()
            .count
            or 0
        )
