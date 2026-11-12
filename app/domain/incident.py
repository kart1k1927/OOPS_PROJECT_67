"""The Incident aggregate.

Everything about an incident changes through a method on this class. There is
no public setter for status, priority or assignee, because every one of those
changes has a rule attached: status goes through the state machine, priority
recalculates the SLA, assignment records who did it. Exposing the fields would
mean those rules could be skipped, which is the whole argument for encapsulation
and the reason this class has thirty properties and no attributes.

Composition: an Incident has-a SLATracker.
Aggregation: an Incident references an ITService and a Category that outlive it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.core.exceptions import InvalidStateTransitionError, ValidationError
from app.domain.catalog import Category, ITService, SLAPolicy
from app.domain.enums import Impact, Priority, SLAState, Status, UpdateType, Urgency
from app.domain.sla import SLATracker
from app.domain.states import IncidentState, state_for

TITLE_MIN = 8
TITLE_MAX = 160


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class IncidentUpdate:
    """One entry in the incident history. Rendered by the activity timeline."""

    incident_id: UUID
    message: str
    update_type: UpdateType = UpdateType.COMMENT
    user_id: UUID | None = None
    old_status: str | None = None
    new_status: str | None = None
    created_at: datetime = field(default_factory=_now)
    id: UUID | None = None
    author_name: str = "System"

    @property
    def is_status_change(self) -> bool:
        return self.update_type is UpdateType.STATUS_CHANGE


class Incident:
    def __init__(
        self,
        *,
        reporter_id: UUID,
        title: str,
        description: str | None = None,
        impact: Impact = Impact.MEDIUM,
        urgency: Urgency = Urgency.MEDIUM,
        affected_users_count: int = 1,
        service: ITService | None = None,
        category: Category | None = None,
        priority: Priority = Priority.P3,
        priority_score: float | None = None,
        status: Status = Status.OPEN,
        assigned_technician_id: UUID | None = None,
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        first_response_at: datetime | None = None,
        acknowledged_at: datetime | None = None,
        resolved_at: datetime | None = None,
        verified_at: datetime | None = None,
        closed_at: datetime | None = None,
        sla: SLATracker | None = None,
        escalation_level: int = 0,
        resolution_notes: str | None = None,
        closure_notes: str | None = None,
        duplicate_of_id: UUID | None = None,
        feedback_rating: int | None = None,
        feedback_comment: str | None = None,
        reporter_name: str = "",
        technician_name: str = "",
        updates: list[IncidentUpdate] | None = None,
    ) -> None:
        self._id = id or uuid4()
        self._reporter_id = reporter_id
        self._title = self._validated_title(title)
        self._description = (description or "").strip() or None
        self._impact = Impact(impact)
        self._urgency = Urgency(urgency)
        self._affected_users_count = self._validated_affected(affected_users_count)
        self._service = service
        self._category = category
        self._priority = Priority(priority)
        self._priority_score = priority_score
        self._status = Status(status)
        self._state: IncidentState = state_for(self._status)
        self._assigned_technician_id = assigned_technician_id
        self._created_at = created_at or _now()
        self._updated_at = updated_at or self._created_at
        self._first_response_at = first_response_at
        self._acknowledged_at = acknowledged_at
        self._resolved_at = resolved_at
        self._verified_at = verified_at
        self._closed_at = closed_at
        self._sla = sla or SLATracker(created_at=self._created_at)
        self._escalation_level = escalation_level
        self._resolution_notes = resolution_notes
        self._closure_notes = closure_notes
        self._duplicate_of_id = duplicate_of_id
        self._feedback_rating = feedback_rating
        self._feedback_comment = feedback_comment
        self._reporter_name = reporter_name
        self._technician_name = technician_name
        self._updates: list[IncidentUpdate] = list(updates or [])

    # --- validation ---------------------------------------------------------

    @staticmethod
    def _validated_title(title: str) -> str:
        cleaned = (title or "").strip()
        if len(cleaned) < TITLE_MIN:
            raise ValidationError(
                f"Give the incident a title of at least {TITLE_MIN} characters so a technician can triage it.",
                field="title",
            )
        if len(cleaned) > TITLE_MAX:
            raise ValidationError(f"Keep the title under {TITLE_MAX} characters.", field="title")
        return cleaned

    @staticmethod
    def _validated_affected(count: int) -> int:
        try:
            value = int(count)
        except (TypeError, ValueError):
            raise ValidationError("Affected users must be a whole number.", field="affected_users_count") from None
        if value < 1:
            raise ValidationError("At least one person is affected, otherwise there is no incident.", field="affected_users_count")
        if value > 100000:
            raise ValidationError("That is more people than the organisation has.", field="affected_users_count")
        return value

    # --- identity -----------------------------------------------------------

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def reference(self) -> str:
        """The short human id shown everywhere in the UI: INC-8F51D7."""
        return "INC-" + str(self._id).replace("-", "")[:6].upper()

    def __repr__(self) -> str:
        return f"<Incident {self.reference} {self._status.value} {self._priority.value}>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Incident) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    # --- plain readers ------------------------------------------------------

    @property
    def reporter_id(self) -> UUID:
        return self._reporter_id

    @property
    def reporter_name(self) -> str:
        return self._reporter_name

    @property
    def technician_name(self) -> str:
        return self._technician_name

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def impact(self) -> Impact:
        return self._impact

    @property
    def urgency(self) -> Urgency:
        return self._urgency

    @property
    def affected_users_count(self) -> int:
        return self._affected_users_count

    @property
    def service(self) -> ITService | None:
        return self._service

    @property
    def category(self) -> Category | None:
        return self._category

    @property
    def priority(self) -> Priority:
        return self._priority

    @property
    def priority_score(self) -> float | None:
        return self._priority_score

    @property
    def status(self) -> Status:
        return self._status

    @property
    def state(self) -> IncidentState:
        return self._state

    @property
    def assigned_technician_id(self) -> UUID | None:
        return self._assigned_technician_id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def first_response_at(self) -> datetime | None:
        return self._first_response_at

    @property
    def acknowledged_at(self) -> datetime | None:
        return self._acknowledged_at

    @property
    def resolved_at(self) -> datetime | None:
        return self._resolved_at

    @property
    def verified_at(self) -> datetime | None:
        return self._verified_at

    @property
    def closed_at(self) -> datetime | None:
        return self._closed_at

    @property
    def sla(self) -> SLATracker:
        return self._sla

    @property
    def escalation_level(self) -> int:
        return self._escalation_level

    @property
    def resolution_notes(self) -> str | None:
        return self._resolution_notes

    @property
    def closure_notes(self) -> str | None:
        return self._closure_notes

    @property
    def duplicate_of_id(self) -> UUID | None:
        return self._duplicate_of_id

    @property
    def feedback_rating(self) -> int | None:
        return self._feedback_rating

    @property
    def feedback_comment(self) -> str | None:
        return self._feedback_comment

    @property
    def updates(self) -> tuple[IncidentUpdate, ...]:
        """A copy, so callers cannot append to the history behind our back."""
        return tuple(self._updates)

    # --- derived ------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._status.is_open

    @property
    def is_assigned(self) -> bool:
        return self._assigned_technician_id is not None

    @property
    def age(self) -> timedelta:
        return _now() - self._created_at

    @property
    def sla_state(self) -> SLAState:
        return self._sla.state(resolved_at=self._resolved_at)

    @property
    def business_criticality(self) -> int:
        return self._service.business_criticality if self._service else 3

    def time_to_resolve(self) -> timedelta | None:
        return (self._resolved_at - self._created_at) if self._resolved_at else None

    def allowed_transitions(self) -> frozenset[Status]:
        return self._state.allowed_transitions()

    # --- behaviour ------------------------------------------------------------

    def _touch(self) -> None:
        self._updated_at = _now()

    def _record(
        self,
        message: str,
        *,
        update_type: UpdateType = UpdateType.SYSTEM,
        user_id: UUID | None = None,
        old_status: str | None = None,
        new_status: str | None = None,
        author_name: str = "System",
    ) -> IncidentUpdate:
        entry = IncidentUpdate(
            incident_id=self._id,
            message=message,
            update_type=update_type,
            user_id=user_id,
            old_status=old_status,
            new_status=new_status,
            author_name=author_name,
        )
        self._updates.append(entry)
        return entry

    def transition_to(
        self,
        target: Status,
        *,
        actor_id: UUID | None = None,
        actor_name: str = "System",
        note: str | None = None,
    ) -> IncidentUpdate:
        """The only way status ever changes.

        Raises InvalidStateTransitionError rather than returning False, because
        a caller that ignores a boolean would carry on as if the incident had
        moved. This is what makes OPEN -> CLOSED impossible.
        """
        target = Status(target)
        if not self._state.permits(target):
            raise InvalidStateTransitionError(self._status, target, hint=self._state.hint())

        previous = self._status
        self._status = target
        self._state = state_for(target)
        self._state.on_enter(self)
        self._touch()

        message = note or f"Status changed from {previous.value} to {target.value}."
        return self._record(
            message,
            update_type=UpdateType.STATUS_CHANGE,
            user_id=actor_id,
            old_status=previous.value,
            new_status=target.value,
            author_name=actor_name,
        )

    def classify(self, category: Category, *, actor_id: UUID | None = None, actor_name: str = "System") -> None:
        self._category = category
        self._touch()
        self._record(
            f"Incident classified as {category.name.upper()}.",
            user_id=actor_id,
            author_name=actor_name,
        )
        if self._status is Status.OPEN:
            self.transition_to(Status.CLASSIFIED, actor_id=actor_id, actor_name=actor_name,
                               note=f"Classified as {category.name.upper()}.")

    def apply_priority(
        self,
        priority: Priority,
        *,
        score: float | None = None,
        policy: SLAPolicy | None = None,
        actor_id: UUID | None = None,
        actor_name: str = "System",
        reason: str = "",
    ) -> None:
        """Set priority and keep the SLA consistent with it.

        Priority and deadlines cannot drift apart, because the only way to
        change one is this method, which changes both.
        """
        previous = self._priority
        self._priority = Priority(priority)
        self._priority_score = score
        if policy is not None:
            self._sla.recalculate(policy)
        self._touch()
        if previous != self._priority:
            detail = f" {reason}" if reason else ""
            self._record(
                f"Priority {previous.value} changed to {self._priority.value} ({self._priority.label}).{detail}",
                user_id=actor_id,
                author_name=actor_name,
            )
        elif score is not None and not self._updates:
            self._record(
                f"Priority calculated as {self._priority.value} ({self._priority.label}). {reason}".strip(),
                user_id=actor_id,
                author_name=actor_name,
            )

    def assign_to(
        self,
        technician_id: UUID,
        *,
        technician_name: str = "",
        strategy: str = "",
        actor_id: UUID | None = None,
        actor_name: str = "System",
    ) -> None:
        reassignment = self._assigned_technician_id is not None
        self._assigned_technician_id = technician_id
        self._technician_name = technician_name or self._technician_name
        self._touch()

        who = technician_name or str(technician_id)[:8]
        verb = "reassigned to" if reassignment else "assigned to"
        via = f" via {strategy}." if strategy else "."
        self._record(
            f"Incident {verb} {who}{via}",
            update_type=UpdateType.ASSIGNMENT,
            user_id=actor_id,
            author_name=actor_name,
        )
        if self._status in (Status.OPEN, Status.CLASSIFIED):
            self.transition_to(Status.ASSIGNED, actor_id=actor_id, actor_name=actor_name,
                               note=f"Assigned to {who}.")

    def acknowledge(self, *, actor_id: UUID, actor_name: str = "") -> IncidentUpdate:
        return self.transition_to(
            Status.ACKNOWLEDGED,
            actor_id=actor_id,
            actor_name=actor_name,
            note="Technician acknowledged the incident.",
        )

    def start_work(self, *, actor_id: UUID, actor_name: str = "") -> IncidentUpdate:
        return self.transition_to(
            Status.IN_PROGRESS, actor_id=actor_id, actor_name=actor_name, note="Investigation started."
        )

    def resolve(self, notes: str, *, actor_id: UUID, actor_name: str = "") -> IncidentUpdate:
        cleaned = (notes or "").strip()
        if len(cleaned) < 10:
            raise ValidationError(
                "Describe what fixed it in at least 10 characters. The reporter and the next technician both read this.",
                field="resolution_notes",
            )
        self._resolution_notes = cleaned
        return self.transition_to(
            Status.RESOLVED, actor_id=actor_id, actor_name=actor_name, note=f"Resolution provided. {cleaned}"
        )

    def reopen(self, reason: str, *, actor_id: UUID, actor_name: str = "") -> IncidentUpdate:
        return self.transition_to(
            Status.IN_PROGRESS,
            actor_id=actor_id,
            actor_name=actor_name,
            note=f"Reopened by the reporter. {reason}".strip(),
        )

    def verify(self, *, actor_id: UUID, actor_name: str = "") -> IncidentUpdate:
        return self.transition_to(
            Status.VERIFIED, actor_id=actor_id, actor_name=actor_name, note="Reporter confirmed the fix."
        )

    def close(self, notes: str | None = None, *, actor_id: UUID, actor_name: str = "") -> IncidentUpdate:
        self._closure_notes = (notes or "").strip() or None
        return self.transition_to(
            Status.CLOSED, actor_id=actor_id, actor_name=actor_name, note=notes or "Incident closed."
        )

    def add_note(self, message: str, *, actor_id: UUID, actor_name: str = "") -> IncidentUpdate:
        cleaned = (message or "").strip()
        if not cleaned:
            raise ValidationError("The note is empty.", field="message")
        if len(cleaned) > 2000:
            raise ValidationError("Keep a note under 2000 characters.", field="message")
        self._touch()
        return self._record(cleaned, update_type=UpdateType.COMMENT, user_id=actor_id, author_name=actor_name)

    def escalate(self, to_level: int, *, reason: str) -> IncidentUpdate:
        self._escalation_level = to_level
        self._touch()
        return self._record(f"Escalated to level {to_level}. {reason}".strip())

    def mark_duplicate_of(self, other_id: UUID, *, other_reference: str = "") -> IncidentUpdate:
        if other_id == self._id:
            raise ValidationError("An incident cannot be a duplicate of itself.")
        self._duplicate_of_id = other_id
        self._touch()
        return self._record(f"Flagged as potentially the same problem as {other_reference or str(other_id)[:8]}.")

    def record_feedback(self, rating: int, comment: str | None = None) -> IncidentUpdate:
        if self._status not in (Status.RESOLVED, Status.VERIFIED, Status.CLOSED):
            raise ValidationError("Feedback can only be given once the incident has been resolved.")
        try:
            value = int(rating)
        except (TypeError, ValueError):
            raise ValidationError("Rating must be a number from 1 to 5.", field="feedback_rating") from None
        if not 1 <= value <= 5:
            raise ValidationError("Rating must be between 1 and 5.", field="feedback_rating")
        self._feedback_rating = value
        self._feedback_comment = (comment or "").strip() or None
        self._touch()
        return self._record(f"Reporter rated the resolution {value} out of 5.")

    def refresh_sla(self, *, now: datetime | None = None) -> bool:
        return self._sla.refresh_flags(
            first_response_at=self._first_response_at,
            resolved_at=self._resolved_at,
            status_is_open=self.is_open,
            now=now,
        )
