"""SLA tracking, composed into every Incident.

An Incident has-a SLATracker. The tracker owns the deadline arithmetic and the
on track / at risk / breached judgement; the incident owns the timestamps that
feed it. Splitting them keeps the incident from becoming a bag of nine date
fields with logic smeared across it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.catalog import SLAPolicy
from app.domain.enums import SLAState

AT_RISK_FRACTION = 0.75
"""Past 75 percent of the window with no resolution, the incident is at risk.
Used by the SLA risk feature and by the colour of the meter in the UI."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SLATracker:
    def __init__(
        self,
        *,
        created_at: datetime,
        policy: SLAPolicy | None = None,
        response_deadline_at: datetime | None = None,
        resolution_deadline_at: datetime | None = None,
        escalation_deadline_at: datetime | None = None,
        response_breached: bool = False,
        resolution_breached: bool = False,
        escalation_breached: bool = False,
    ) -> None:
        self._created_at = created_at
        self._policy = policy
        self._response_deadline_at = response_deadline_at
        self._resolution_deadline_at = resolution_deadline_at
        self._escalation_deadline_at = escalation_deadline_at
        self._response_breached = response_breached
        self._resolution_breached = resolution_breached
        self._escalation_breached = escalation_breached
        if policy is not None and resolution_deadline_at is None:
            self.recalculate(policy)

    # --- deadlines ----------------------------------------------------------

    def recalculate(self, policy: SLAPolicy) -> None:
        """Applied on creation and whenever priority changes."""
        self._policy = policy
        self._response_deadline_at = self._created_at + policy.response_target
        self._resolution_deadline_at = self._created_at + policy.resolution_target
        self._escalation_deadline_at = self._created_at + policy.escalation_target

    @property
    def policy(self) -> SLAPolicy | None:
        return self._policy

    @property
    def response_deadline_at(self) -> datetime | None:
        return self._response_deadline_at

    @property
    def resolution_deadline_at(self) -> datetime | None:
        return self._resolution_deadline_at

    @property
    def escalation_deadline_at(self) -> datetime | None:
        return self._escalation_deadline_at

    @property
    def response_breached(self) -> bool:
        return self._response_breached

    @property
    def resolution_breached(self) -> bool:
        return self._resolution_breached

    @property
    def escalation_breached(self) -> bool:
        return self._escalation_breached

    # --- judgement ----------------------------------------------------------

    def refresh_flags(self, *, first_response_at, resolved_at, status_is_open: bool, now: datetime | None = None) -> bool:
        """Recompute the three breach booleans. Returns True if any changed,
        so the caller knows whether a write and a notification are needed."""
        now = now or _now()
        before = (self._response_breached, self._resolution_breached, self._escalation_breached)

        self._response_breached = (
            first_response_at is None
            and self._response_deadline_at is not None
            and self._response_deadline_at < now
        )
        self._resolution_breached = (
            resolved_at is None
            and self._resolution_deadline_at is not None
            and self._resolution_deadline_at < now
        )
        self._escalation_breached = (
            status_is_open
            and self._escalation_deadline_at is not None
            and self._escalation_deadline_at < now
        )
        return before != (self._response_breached, self._resolution_breached, self._escalation_breached)

    def resolution_remaining(self, *, resolved_at=None, now: datetime | None = None) -> timedelta | None:
        if self._resolution_deadline_at is None:
            return None
        reference = resolved_at or now or _now()
        return self._resolution_deadline_at - reference

    def elapsed_fraction(self, *, resolved_at=None, now: datetime | None = None) -> float:
        """0.0 at creation, 1.0 at the deadline, above 1.0 once breached."""
        if self._resolution_deadline_at is None:
            return 0.0
        window = (self._resolution_deadline_at - self._created_at).total_seconds()
        if window <= 0:
            return 1.0
        reference = resolved_at or now or _now()
        return max(0.0, (reference - self._created_at).total_seconds() / window)

    def state(self, *, resolved_at=None, now: datetime | None = None) -> SLAState:
        if self._resolution_deadline_at is None:
            return SLAState.NOT_APPLICABLE
        now = now or _now()
        if resolved_at is not None:
            return SLAState.BREACHED if resolved_at > self._resolution_deadline_at else SLAState.MET
        if now > self._resolution_deadline_at:
            return SLAState.BREACHED
        if self.elapsed_fraction(now=now) >= AT_RISK_FRACTION:
            return SLAState.AT_RISK
        return SLAState.ON_TRACK

    def escalation_due(self, *, status_is_open: bool, now: datetime | None = None) -> bool:
        now = now or _now()
        return (
            status_is_open
            and self._escalation_deadline_at is not None
            and self._escalation_deadline_at < now
        )
