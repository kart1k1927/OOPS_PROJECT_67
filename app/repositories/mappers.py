"""Row to object and back.

All knowledge of column names lives here. The domain does not know that
`resolution_deadline_at` is spelled that way, and the repositories do not know
how an Incident keeps its state. Changing a column name is a change to this one
file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.domain.catalog import Category, ITService, SLAPolicy
from app.domain.enums import Impact, Priority, Status, UpdateType, Urgency
from app.domain.incident import Incident, IncidentUpdate
from app.domain.factories import UserFactory
from app.domain.sla import SLATracker


def parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        # Postgres sometimes returns more than six fractional digits.
        head, _, tail = text.partition(".")
        digits = "".join(c for c in tail if c.isdigit())[:6]
        offset = tail[len(digits):] if len(tail) > len(digits) else ""
        parsed = datetime.fromisoformat(f"{head}.{digits or '0'}{offset}")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_uuid(value) -> UUID | None:
    if value in (None, "", "None"):
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


# --- catalogue ----------------------------------------------------------------


def to_category(row: dict) -> Category:
    return Category(id=parse_uuid(row["id"]), name=row["name"], description=row.get("description"))


def to_service(row: dict) -> ITService:
    return ITService(
        id=parse_uuid(row["id"]),
        name=row["name"],
        business_criticality=int(row.get("business_criticality") or 3),
        description=row.get("description"),
        is_active=bool(row.get("is_active", True)),
    )


def to_sla_policy(row: dict) -> SLAPolicy:
    return SLAPolicy(
        id=parse_uuid(row.get("id")),
        priority=Priority(row["priority"]),
        response_hours=float(row["response_hours"]),
        resolution_hours=float(row["resolution_hours"]),
        escalation_hours=float(row["escalation_hours"]),
    )


# --- users ----------------------------------------------------------------------


def to_user(row: dict, *, skills: set[UUID] | None = None, skill_names: tuple[str, ...] = (), active_workload: int = 0, resolved_count: int = 0):
    return UserFactory.create(
        row.get("role", "EMPLOYEE"),
        id=parse_uuid(row["id"]),
        employee_code=row.get("employee_code") or "EMP???",
        full_name=row.get("full_name") or row.get("employee_code") or "Unnamed user",
        email=row.get("email") or f"{(row.get('employee_code') or 'user').lower()}@placeholder.invalid",
        is_active=bool(row.get("is_active", True)),
        created_at=parse_dt(row.get("created_at")),
        password_hash=row.get("password_hash"),
        skills=skills or set(),
        skill_names=skill_names,
        max_workload=int(row.get("max_workload") or 5),
        experience_level=int(row.get("experience_level") or 1),
        active_workload=active_workload,
        resolved_count=resolved_count,
    )


def user_to_row(user) -> dict:
    row = {
        "id": str(user.id),
        "employee_code": user.employee_code,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "password_hash": user.password_hash,
    }
    if hasattr(user, "max_workload"):
        row["max_workload"] = user.max_workload
        row["experience_level"] = user.experience_level
    return row


# --- incidents --------------------------------------------------------------------


def to_incident(
    row: dict,
    *,
    services: dict[UUID, ITService] | None = None,
    categories: dict[UUID, Category] | None = None,
    policies: dict[Priority, SLAPolicy] | None = None,
    updates: list[IncidentUpdate] | None = None,
) -> Incident:
    services = services or {}
    categories = categories or {}
    policies = policies or {}

    service_id = parse_uuid(row.get("service_id"))
    category_id = parse_uuid(row.get("category_id"))
    priority = Priority(row.get("priority") or "P3")
    created_at = parse_dt(row.get("created_at")) or datetime.now(timezone.utc)

    sla = SLATracker(
        created_at=created_at,
        policy=policies.get(priority),
        response_deadline_at=parse_dt(row.get("response_deadline_at")),
        resolution_deadline_at=parse_dt(row.get("resolution_deadline_at")),
        escalation_deadline_at=parse_dt(row.get("escalation_deadline_at")),
        response_breached=bool(row.get("response_breached")),
        resolution_breached=bool(row.get("resolution_breached")),
        escalation_breached=bool(row.get("escalation_breached")),
    )

    reporter = row.get("reporter") or {}
    technician = row.get("technician") or {}

    return Incident(
        id=parse_uuid(row["id"]),
        reporter_id=parse_uuid(row["reporter_id"]),
        reporter_name=reporter.get("full_name") or reporter.get("employee_code") or "",
        technician_name=technician.get("full_name") or technician.get("employee_code") or "",
        title=row.get("title") or "Untitled incident",
        description=row.get("description"),
        impact=Impact(row.get("impact") or "MEDIUM"),
        urgency=Urgency(row.get("urgency") or "MEDIUM"),
        affected_users_count=int(row.get("affected_users_count") or 1),
        service=services.get(service_id),
        category=categories.get(category_id),
        priority=priority,
        priority_score=float(row["priority_score"]) if row.get("priority_score") is not None else None,
        status=Status(row.get("status") or "OPEN"),
        assigned_technician_id=parse_uuid(row.get("assigned_technician_id")),
        created_at=created_at,
        updated_at=parse_dt(row.get("updated_at")),
        first_response_at=parse_dt(row.get("first_response_at")),
        acknowledged_at=parse_dt(row.get("acknowledged_at")),
        resolved_at=parse_dt(row.get("resolved_at")),
        verified_at=parse_dt(row.get("verified_at")),
        closed_at=parse_dt(row.get("closed_at")),
        sla=sla,
        escalation_level=int(row.get("escalation_level") or 0),
        resolution_notes=row.get("resolution_notes"),
        closure_notes=row.get("closure_notes"),
        duplicate_of_id=parse_uuid(row.get("duplicate_of_id")),
        feedback_rating=row.get("feedback_rating"),
        feedback_comment=row.get("feedback_comment"),
        updates=updates or [],
    )


def incident_to_row(incident: Incident) -> dict:
    return {
        "id": str(incident.id),
        "reporter_id": str(incident.reporter_id),
        "service_id": str(incident.service.id) if incident.service else None,
        "category_id": str(incident.category.id) if incident.category else None,
        "title": incident.title,
        "description": incident.description,
        "impact": incident.impact.value,
        "urgency": incident.urgency.value,
        "affected_users_count": incident.affected_users_count,
        "priority": incident.priority.value,
        "priority_score": incident.priority_score,
        "status": incident.status.value,
        "assigned_technician_id": str(incident.assigned_technician_id) if incident.assigned_technician_id else None,
        "created_at": iso(incident.created_at),
        "first_response_at": iso(incident.first_response_at),
        "acknowledged_at": iso(incident.acknowledged_at),
        "resolved_at": iso(incident.resolved_at),
        "verified_at": iso(incident.verified_at),
        "closed_at": iso(incident.closed_at),
        "response_deadline_at": iso(incident.sla.response_deadline_at),
        "resolution_deadline_at": iso(incident.sla.resolution_deadline_at),
        "escalation_deadline_at": iso(incident.sla.escalation_deadline_at),
        "response_breached": incident.sla.response_breached,
        "resolution_breached": incident.sla.resolution_breached,
        "escalation_breached": incident.sla.escalation_breached,
        "escalation_level": incident.escalation_level,
        "resolution_notes": incident.resolution_notes,
        "closure_notes": incident.closure_notes,
        "duplicate_of_id": str(incident.duplicate_of_id) if incident.duplicate_of_id else None,
        "feedback_rating": incident.feedback_rating,
        "feedback_comment": incident.feedback_comment,
    }


def to_update(row: dict) -> IncidentUpdate:
    author = row.get("author") or {}
    return IncidentUpdate(
        id=parse_uuid(row.get("id")),
        incident_id=parse_uuid(row["incident_id"]),
        user_id=parse_uuid(row.get("user_id")),
        update_type=UpdateType(row.get("update_type") or "COMMENT"),
        message=row.get("message") or "",
        old_status=row.get("old_status"),
        new_status=row.get("new_status"),
        created_at=parse_dt(row.get("created_at")),
        author_name=author.get("full_name") or author.get("employee_code") or "System",
    )


def update_to_row(update: IncidentUpdate) -> dict:
    return {
        "incident_id": str(update.incident_id),
        "user_id": str(update.user_id) if update.user_id else None,
        "update_type": update.update_type.value,
        "message": update.message,
        "old_status": update.old_status,
        "new_status": update.new_status,
        "created_at": iso(update.created_at),
    }
