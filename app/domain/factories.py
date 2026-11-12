"""Factory pattern.

Two things are built here, and both have the same justification: constructing
them correctly takes knowledge that the caller should not need to hold.

  UserFactory      picks the right User subclass from a role string. Routers
                   and repositories never import Employee or Technician.
  IncidentFactory  builds an Incident with its priority already calculated by
                   the current strategy and its SLA deadlines already derived
                   from the matching policy, so an incident with a priority but
                   no deadlines cannot exist.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import SLAPolicyMissingError, ValidationError
from app.domain.catalog import Category, ITService, SLAPolicy
from app.domain.enums import EventType, Impact, Priority, Role, Status, Urgency
from app.domain.events import IncidentEvent
from app.domain.incident import Incident
from app.domain.priority import PriorityStrategy, get_priority_strategy
from app.domain.sla import SLATracker
from app.domain.users import Administrator, Employee, Technician, User


class UserFactory:
    _BY_ROLE = {Role.EMPLOYEE: Employee, Role.TECHNICIAN: Technician, Role.ADMIN: Administrator}

    @classmethod
    def create(cls, role: Role | str, **kwargs) -> User:
        try:
            resolved = Role(role)
        except ValueError:
            raise ValidationError(f"{role} is not a role this system has.", field="role") from None
        klass = cls._BY_ROLE[resolved]
        if klass is not Technician:
            kwargs.pop("skills", None)
            kwargs.pop("max_workload", None)
            kwargs.pop("experience_level", None)
            kwargs.pop("active_workload", None)
            kwargs.pop("resolved_count", None)
            kwargs.pop("skill_names", None)
        return klass(**kwargs)

    @classmethod
    def roles(cls) -> list[str]:
        return [r.value for r in cls._BY_ROLE]


class IncidentFactory:
    """Builds incidents. Owns the rule that priority and SLA arrive together."""

    def __init__(self, priority_strategy: PriorityStrategy | None = None) -> None:
        self._priority_strategy = priority_strategy or get_priority_strategy()

    @property
    def priority_strategy(self) -> PriorityStrategy:
        return self._priority_strategy

    def use_strategy(self, strategy: PriorityStrategy) -> None:
        self._priority_strategy = strategy

    def build(
        self,
        *,
        reporter,
        title: str,
        description: str | None,
        service: ITService | None,
        category: Category | None,
        impact: Impact,
        urgency: Urgency,
        affected_users_count: int,
        policy_lookup,
    ) -> tuple[Incident, list[IncidentEvent]]:
        if service is not None and not service.is_active:
            raise ValidationError(f"{service.name} is not an active service.", field="service_id")

        created_at = datetime.now(timezone.utc)
        decision = self._priority_strategy.calculate(
            impact=Impact(impact),
            urgency=Urgency(urgency),
            business_criticality=service.business_criticality if service else 3,
            affected_users=affected_users_count,
        )

        policy: SLAPolicy | None = policy_lookup(decision.priority)
        if policy is None:
            raise SLAPolicyMissingError(decision.priority.value)

        incident = Incident(
            id=uuid4(),
            reporter_id=reporter.id,
            reporter_name=reporter.full_name,
            title=title,
            description=description,
            service=service,
            category=category,
            impact=Impact(impact),
            urgency=Urgency(urgency),
            affected_users_count=affected_users_count,
            priority=decision.priority,
            priority_score=decision.score,
            status=Status.OPEN,
            created_at=created_at,
            sla=SLATracker(created_at=created_at, policy=policy),
        )

        events = [
            IncidentEvent(
                EventType.INCIDENT_CREATED,
                incident,
                reporter,
                {"detail": f"{incident.reference} created by {reporter.employee_code} ({reporter.full_name})."},
            ),
            IncidentEvent(
                EventType.PRIORITY_CALCULATED,
                incident,
                None,
                {
                    "detail": f"Priority calculated as {decision.priority.value}. {decision.explanation}.",
                    "score": decision.score,
                    "strategy": decision.strategy,
                },
            ),
        ]
        if category is not None:
            events.insert(
                1,
                IncidentEvent(
                    EventType.INCIDENT_CLASSIFIED,
                    incident,
                    reporter,
                    {"detail": f"Incident classified as {category.name.upper()}."},
                ),
            )
        return incident, events


class NotificationFactory:
    """Builds the notification text for an event.

    Centralised so that a channel implementation never writes copy. An email
    adapter and an in-app adapter must say the same thing.
    """

    _TEMPLATES: dict[EventType, tuple[str, str]] = {
        EventType.INCIDENT_CREATED: ("Incident {ref} logged", "We have logged {ref}: {title}. Priority {priority}."),
        EventType.TECHNICIAN_ASSIGNED: ("{ref} assigned to you", "{ref} ({priority}) was assigned to you: {title}."),
        EventType.INCIDENT_ACKNOWLEDGED: ("{ref} acknowledged", "{tech} has picked up {ref} and will investigate."),
        EventType.STATUS_CHANGED: ("{ref} is now {status}", "{ref} moved to {status}: {title}."),
        EventType.PRIORITY_CHANGED: ("{ref} priority is now {priority}", "The priority of {ref} changed to {priority}."),
        EventType.SLA_APPROACHING: ("{ref} is close to its SLA", "{ref} ({priority}) must be resolved soon. {remaining} left."),
        EventType.SLA_VIOLATED: ("{ref} has breached its SLA", "{ref} ({priority}) passed its resolution deadline."),
        EventType.INCIDENT_ESCALATED: ("{ref} escalated", "{ref} was escalated because it was not acknowledged in time."),
        EventType.DUPLICATE_DETECTED: ("{ref} may be a duplicate", "{ref} looks like an existing problem. {detail}"),
        EventType.INCIDENT_RESOLVED: ("{ref} has been resolved", "{ref} was resolved: {title}. Confirm the fix or reopen it."),
        EventType.INCIDENT_VERIFIED: ("{ref} confirmed by the reporter", "The reporter confirmed the fix for {ref}."),
        EventType.INCIDENT_CLOSED: ("{ref} closed", "{ref} is closed. Thank you."),
    }

    @classmethod
    def build(cls, event: IncidentEvent) -> tuple[str, str] | None:
        template = cls._TEMPLATES.get(event.type)
        if template is None:
            return None
        incident = event.incident
        context = {
            "ref": getattr(incident, "reference", ""),
            "title": getattr(incident, "title", ""),
            "priority": getattr(getattr(incident, "priority", None), "value", ""),
            "status": getattr(getattr(incident, "status", None), "label", ""),
            "tech": getattr(incident, "technician_name", "A technician") or "A technician",
            "remaining": event.payload.get("remaining", "Not long"),
            "detail": event.payload.get("detail", ""),
        }
        title, body = template
        return title.format(**context), body.format(**context)
