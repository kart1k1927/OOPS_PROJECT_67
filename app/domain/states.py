"""State pattern for the incident lifecycle.

The problem statement requires that inappropriate transitions be prevented, and
names NEW -> CLOSED as the example that must fail. The transition table lives
in one class per state rather than in an if/elif chain, so adding a state means
adding a class and touching nothing else.

    OPEN -> CLASSIFIED -> ASSIGNED -> ACKNOWLEDGED -> IN_PROGRESS
         -> RESOLVED -> VERIFIED -> CLOSED

with PENDING as a side branch off ACKNOWLEDGED and IN_PROGRESS for when a
technician is waiting on the reporter, and RESOLVED -> IN_PROGRESS for a fix
that did not hold.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.domain.enums import Status


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentState(ABC):
    """One per status. Knows where it may go and what entering it records."""

    status: Status

    @abstractmethod
    def allowed_transitions(self) -> frozenset[Status]:
        """The statuses this state may legally move to."""

    def on_enter(self, incident) -> None:
        """Stamp whatever entering this state records. Default: nothing."""

    def hint(self) -> str:
        """Appended to the error when a transition is refused."""
        nxt = sorted(s.value for s in self.allowed_transitions())
        if not nxt:
            return "A closed incident is final."
        return "Allowed from here: " + ", ".join(nxt) + "."

    def permits(self, target: Status) -> bool:
        return target in self.allowed_transitions()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class OpenState(IncidentState):
    status = Status.OPEN

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.CLASSIFIED, Status.ASSIGNED})


class ClassifiedState(IncidentState):
    status = Status.CLASSIFIED

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.ASSIGNED})


class AssignedState(IncidentState):
    status = Status.ASSIGNED

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.ACKNOWLEDGED, Status.ASSIGNED})


class AcknowledgedState(IncidentState):
    status = Status.ACKNOWLEDGED

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.IN_PROGRESS, Status.PENDING})

    def on_enter(self, incident) -> None:
        stamp = _now()
        incident._acknowledged_at = stamp
        if incident.first_response_at is None:
            incident._first_response_at = stamp


class InProgressState(IncidentState):
    status = Status.IN_PROGRESS

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.PENDING, Status.RESOLVED})

    def on_enter(self, incident) -> None:
        if incident.first_response_at is None:
            incident._first_response_at = _now()


class PendingState(IncidentState):
    status = Status.PENDING

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.IN_PROGRESS})

    def hint(self) -> str:
        return "This incident is waiting on the reporter. Move it back to IN_PROGRESS to continue."


class ResolvedState(IncidentState):
    status = Status.RESOLVED

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.VERIFIED, Status.IN_PROGRESS})

    def on_enter(self, incident) -> None:
        incident._resolved_at = _now()


class VerifiedState(IncidentState):
    status = Status.VERIFIED

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset({Status.CLOSED})

    def on_enter(self, incident) -> None:
        incident._verified_at = _now()


class ClosedState(IncidentState):
    status = Status.CLOSED

    def allowed_transitions(self) -> frozenset[Status]:
        return frozenset()

    def on_enter(self, incident) -> None:
        incident._closed_at = _now()

    def hint(self) -> str:
        return "A closed incident is final. Report a new incident instead."


_STATES: dict[Status, IncidentState] = {
    s.status: s
    for s in (
        OpenState(),
        ClassifiedState(),
        AssignedState(),
        AcknowledgedState(),
        InProgressState(),
        PendingState(),
        ResolvedState(),
        VerifiedState(),
        ClosedState(),
    )
}


def state_for(status: Status) -> IncidentState:
    """Flyweight lookup. States hold no per-incident data, so one instance of
    each is shared by every incident in that status."""
    return _STATES[Status(status)]


def transition_graph() -> dict[str, list[str]]:
    """Used by the admin settings screen and by the test suite."""
    return {s.value: sorted(t.value for t in state_for(s).allowed_transitions()) for s in Status}
