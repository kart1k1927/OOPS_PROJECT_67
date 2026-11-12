"""Use case orchestration.

Routers call this and nothing else. It holds no business rules of its own: the
state machine decides what may happen, the strategies decide who and how
urgently, the observers decide who hears about it. What this class contributes
is sequence, authorisation and persistence.

Every write goes through perform(), which calls User.require_action first. That
single funnel is why a crafted POST cannot do something the interface does not
offer: authorisation and the state machine are checked in the same place, for
every action, by construction rather than by remembering to.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import (
    CategoryNotFoundError,
    IncidentNotFoundError,
    ServiceNotFoundError,
    UnauthorizedOperationError,
    UserNotFoundError,
    ValidationError,
)
from app.domain.enums import EventType, Impact, Priority, Status, Urgency
from app.domain.events import IncidentEvent
from app.domain.factories import IncidentFactory
from app.domain.incident import Incident
from app.repositories.base import IncidentQuery
from app.services.intelligence.categorizer import IncidentCategorizer
from app.services.intelligence.duplicate_detector import DuplicateDetector
from app.services.intelligence.recommender import ResolutionRecommender, TechnicianRecommender

logger = logging.getLogger(__name__)


class IncidentService:
    def __init__(
        self,
        *,
        incidents,
        users,
        catalog,
        event_bus,
        settings,
        duplicate_detector: DuplicateDetector | None = None,
        categorizer: IncidentCategorizer | None = None,
        technician_recommender: TechnicianRecommender | None = None,
        resolution_recommender: ResolutionRecommender | None = None,
    ) -> None:
        self._incidents = incidents
        self._users = users
        self._catalog = catalog
        self._bus = event_bus
        self._settings = settings
        self._duplicates = duplicate_detector or DuplicateDetector(incidents)
        self._categorizer = categorizer or IncidentCategorizer()
        self._tech_recommender = technician_recommender or TechnicianRecommender(incidents)
        self._resolutions = resolution_recommender or ResolutionRecommender(incidents)

    # --- reads ----------------------------------------------------------------

    def get_for(self, user, incident_id: UUID, *, with_updates: bool = True) -> Incident:
        incident = self._incidents.get(incident_id, with_updates=with_updates)
        if incident is None:
            raise IncidentNotFoundError(str(incident_id)[:8])
        user.require_can_view(incident)
        return incident

    def search_for(self, user, query: IncidentQuery) -> list[Incident]:
        """Scope the query to what this role may see, then run it.

        The scoping is polymorphic: an Employee is pinned to their own reports,
        a Technician to their queue, an Administrator to everything."""
        from app.domain.users import Administrator, Employee, Technician

        if isinstance(user, Employee):
            query.reporter_id = user.id
        elif isinstance(user, Technician) and query.technician_id is None and not query.unassigned_only:
            query.technician_id = user.id
        return self._incidents.search(query)

    def count_for(self, user, query: IncidentQuery) -> int:
        from app.domain.users import Employee, Technician

        if isinstance(user, Employee):
            query.reporter_id = user.id
        elif isinstance(user, Technician) and query.technician_id is None and not query.unassigned_only:
            query.technician_id = user.id
        return self._incidents.count(query)

    # --- helpers for the report form -------------------------------------------

    def preview_priority(self, *, impact: Impact, urgency: Urgency, service_id: UUID | None, affected_users: int):
        service = self._catalog.get_service(service_id) if service_id else None
        return self._settings.priority_strategy.calculate(
            impact=Impact(impact),
            urgency=Urgency(urgency),
            business_criticality=service.business_criticality if service else 3,
            affected_users=max(1, int(affected_users or 1)),
        )

    def suggest_category(self, title: str, description: str | None = None):
        if not self._settings.auto_categorize:
            return None
        return self._categorizer.suggest(title, description)

    def find_duplicates(self, incident, *, limit: int = 3):
        if not self._settings.duplicate_detection:
            return []
        return self._duplicates.find(incident, limit=limit)

    def recommend_technicians(self, incident, *, limit: int = 5):
        return self._tech_recommender.rank(incident, self._users.list_technicians(), limit=limit)

    def suggest_resolutions(self, incident, *, limit: int = 3):
        return self._resolutions.suggest(incident, limit=limit)

    def correlated_clusters(self):
        return self._duplicates.correlate(self._incidents.open_incidents())

    # --- persistence ------------------------------------------------------------

    def _commit(self, incident: Incident, watermark: int) -> None:
        """Persist the incident and only the history entries added since the
        watermark, so an update is never written twice."""
        self._incidents.update(incident)
        for entry in incident.updates[watermark:]:
            self._incidents.add_update(entry)

    # --- creating ----------------------------------------------------------------

    def report(
        self,
        *,
        reporter,
        title: str,
        description: str | None,
        service_id: UUID | None,
        category_id: UUID | None,
        impact: Impact,
        urgency: Urgency,
        affected_users_count: int,
        auto_assign: bool | None = None,
    ) -> tuple[Incident, list]:
        service = None
        if service_id:
            service = self._catalog.get_service(service_id)
            if service is None:
                raise ServiceNotFoundError(str(service_id)[:8])

        category = None
        if category_id:
            category = self._catalog.get_category(category_id)
            if category is None:
                raise CategoryNotFoundError(str(category_id)[:8])
        else:
            # Auto categorisation fills the gap when the reporter skipped it.
            suggestion = self.suggest_category(title, description)
            if suggestion is not None:
                category = next(
                    (c for c in self._catalog.list_categories() if c.name == suggestion.category_name), None
                )

        factory = IncidentFactory(self._settings.priority_strategy)
        incident, events = factory.build(
            reporter=reporter,
            title=title,
            description=description,
            service=service,
            category=category,
            impact=impact,
            urgency=urgency,
            affected_users_count=affected_users_count,
            policy_lookup=self._catalog.get_sla_policy,
        )

        duplicates = self.find_duplicates(incident)
        if duplicates:
            best = duplicates[0]
            incident.mark_duplicate_of(best.incident.id, other_reference=best.reference)
            events.append(
                IncidentEvent(
                    EventType.DUPLICATE_DETECTED,
                    incident,
                    None,
                    {"detail": f"Possible duplicate. {best.explain()}.", "duplicate_of": best.reference},
                )
            )

        self._incidents.add(incident)

        should_assign = self._settings.auto_assign if auto_assign is None else auto_assign
        if should_assign:
            try:
                self._assign_by_strategy(incident, actor=None, events=events)
            except Exception as exc:  # an unassignable incident is still a real incident
                logger.warning("Auto assignment failed for %s: %s", incident.reference, exc)
                events.append(
                    IncidentEvent(
                        EventType.STATUS_CHANGED,
                        incident,
                        None,
                        {"detail": f"Automatic assignment did not find a technician. {exc}"},
                    )
                )

        self._commit(incident, 0)
        self._bus.publish_many(events)
        return incident, duplicates

    # --- assignment ------------------------------------------------------------------

    def _assign_by_strategy(self, incident: Incident, *, actor, events: list) -> None:
        strategy = self._settings.assignment_strategy
        technicians = self._users.list_technicians()
        decision = strategy.select(incident, technicians)
        technician = decision.technician
        incident.assign_to(
            technician.id,
            technician_name=technician.full_name,
            strategy=strategy.label,
            actor_id=getattr(actor, "id", None),
            actor_name=getattr(actor, "full_name", "System"),
        )
        events.append(
            IncidentEvent(
                EventType.TECHNICIAN_ASSIGNED,
                incident,
                actor,
                {
                    "detail": f"Assigned to {technician.employee_code} ({technician.full_name}). {decision.reason}.",
                    "strategy": decision.strategy,
                    "technician": str(technician.id),
                },
            )
        )

    def assign(self, *, actor, incident_id: UUID, technician_id: UUID | None = None) -> Incident:
        incident = self.get_for(actor, incident_id)
        actor.require_action(incident, "assign")
        watermark = len(incident.updates)
        events: list = []

        if technician_id is None:
            self._assign_by_strategy(incident, actor=actor, events=events)
        else:
            technician = self._users.get(technician_id)
            if technician is None or technician.role.value != "TECHNICIAN":
                raise UserNotFoundError(str(technician_id)[:8])
            if not technician.is_active:
                raise ValidationError(f"{technician.full_name} is not an active technician.")
            incident.assign_to(
                technician.id,
                technician_name=technician.full_name,
                strategy="manual assignment",
                actor_id=actor.id,
                actor_name=actor.full_name,
            )
            events.append(
                IncidentEvent(
                    EventType.TECHNICIAN_ASSIGNED,
                    incident,
                    actor,
                    {"detail": f"Assigned to {technician.employee_code} ({technician.full_name}) by {actor.full_name}."},
                )
            )

        self._commit(incident, watermark)
        self._bus.publish_many(events)
        return incident

    def change_priority(self, *, actor, incident_id: UUID, priority: Priority, reason: str = "") -> Incident:
        incident = self.get_for(actor, incident_id)
        actor.require_action(incident, "change_priority")
        watermark = len(incident.updates)
        previous = incident.priority
        policy = self._catalog.get_sla_policy(Priority(priority))
        incident.apply_priority(
            Priority(priority),
            score=incident.priority_score,
            policy=policy,
            actor_id=actor.id,
            actor_name=actor.full_name,
            reason=reason or f"Changed by {actor.full_name}.",
        )
        self._commit(incident, watermark)
        self._bus.publish(
            IncidentEvent(
                EventType.PRIORITY_CHANGED,
                incident,
                actor,
                {"detail": f"Priority changed from {previous.value} to {incident.priority.value} by {actor.full_name}."},
            )
        )
        return incident

    # --- the single authorised write path -----------------------------------------

    _TRANSITION_EVENTS = {
        Status.ACKNOWLEDGED: EventType.INCIDENT_ACKNOWLEDGED,
        Status.RESOLVED: EventType.INCIDENT_RESOLVED,
        Status.VERIFIED: EventType.INCIDENT_VERIFIED,
        Status.CLOSED: EventType.INCIDENT_CLOSED,
    }

    def perform(self, *, actor, incident_id: UUID, action_key: str, note: str | None = None, **extra) -> Incident:
        incident = self.get_for(actor, incident_id)
        action = actor.require_action(incident, action_key)

        if action.needs_note and not (note or "").strip() and action_key != "resolve":
            raise ValidationError("Add a note explaining this.", field="note")

        watermark = len(incident.updates)
        previous = incident.status

        match action_key:
            case "acknowledge":
                incident.acknowledge(actor_id=actor.id, actor_name=actor.full_name)
            case "start_work" | "resume":
                incident.start_work(actor_id=actor.id, actor_name=actor.full_name)
            case "hold":
                incident.transition_to(
                    Status.PENDING,
                    actor_id=actor.id,
                    actor_name=actor.full_name,
                    note=f"Waiting on the reporter. {note}".strip(),
                )
            case "resolve":
                incident.resolve(note or "", actor_id=actor.id, actor_name=actor.full_name)
            case "reopen":
                incident.reopen(note or "", actor_id=actor.id, actor_name=actor.full_name)
            case "verify":
                incident.verify(actor_id=actor.id, actor_name=actor.full_name)
            case "close":
                incident.close(note, actor_id=actor.id, actor_name=actor.full_name)
            case "add_note":
                incident.add_note(note or "", actor_id=actor.id, actor_name=actor.full_name)
            case "feedback":
                incident.record_feedback(extra.get("rating"), extra.get("comment"))
            case "escalate":
                incident.escalate(
                    min(incident.escalation_level + 1, 3),
                    reason=f"Escalated by {actor.full_name}. {note}".strip(),
                )
            case _:
                raise UnauthorizedOperationError(f"{action_key} is not an action this system performs.")

        self._commit(incident, watermark)

        if action_key == "feedback":
            event_type = EventType.FEEDBACK_RECEIVED
            detail = f"Reporter rated {incident.reference} {incident.feedback_rating} out of 5."
        elif action_key == "add_note":
            event_type = EventType.NOTE_ADDED
            detail = f"{actor.full_name} added a note to {incident.reference}."
        elif action_key == "escalate":
            event_type = EventType.INCIDENT_ESCALATED
            detail = f"{incident.reference} escalated to level {incident.escalation_level} by {actor.full_name}."
        else:
            event_type = self._TRANSITION_EVENTS.get(incident.status, EventType.STATUS_CHANGED)
            detail = f"{incident.reference} moved from {previous.value} to {incident.status.value} by {actor.full_name}."

        self._bus.publish(
            IncidentEvent(
                event_type,
                incident,
                actor,
                {"detail": detail, "previous_state": previous.value, "new_state": incident.status.value},
            )
        )
        return incident
