"""Intelligent feature D: automatic escalation.

The brief's ladder is

    Technician -> Team Lead -> System Administrator -> IT Manager

This system has three roles, so the ladder maps onto them: level 1 is the most
experienced technician available, level 2 is an administrator, level 3 is every
administrator at once. Each rung is a rule, so adding a real Team Lead role
later means changing one table entry.

An incident escalates when its escalation deadline passes while it is still
unacknowledged, or when a P1 goes unacknowledged for a quarter of its
resolution window. Escalation never reassigns the incident, it widens who is
being told, because taking work off a technician who is already on it helps
nobody.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.enums import Role, Status


@dataclass(frozen=True, slots=True)
class EscalationDecision:
    incident: object
    from_level: int
    to_level: int
    tier_name: str
    reason: str

    @property
    def reference(self) -> str:
        return self.incident.reference


class EscalationEngine:
    TIERS = {
        0: "Assigned technician",
        1: "Senior technician",
        2: "System administrator",
        3: "IT management",
    }
    MAX_LEVEL = 3

    UNACKNOWLEDGED = {Status.OPEN, Status.CLASSIFIED, Status.ASSIGNED}

    def __init__(self, user_repository) -> None:
        self._users = user_repository

    def _due(self, incident, now: datetime) -> str | None:
        if not incident.is_open:
            return None
        if incident.escalation_level >= self.MAX_LEVEL:
            return None

        unacknowledged = incident.status in self.UNACKNOWLEDGED
        if unacknowledged and incident.sla.escalation_due(status_is_open=True, now=now):
            minutes = int((now - incident.created_at).total_seconds() // 60)
            return f"Not acknowledged {minutes} minutes after being reported."

        if incident.sla.resolution_breached and incident.escalation_level == 0:
            return "Resolution deadline passed."
        return None

    def evaluate(self, incident, *, now: datetime | None = None) -> EscalationDecision | None:
        now = now or datetime.now(timezone.utc)
        reason = self._due(incident, now)
        if reason is None:
            return None
        to_level = min(incident.escalation_level + 1, self.MAX_LEVEL)
        return EscalationDecision(
            incident=incident,
            from_level=incident.escalation_level,
            to_level=to_level,
            tier_name=self.TIERS[to_level],
            reason=reason,
        )

    def recipients_for(self, level: int) -> list:
        """Who gets told at this rung."""
        if level <= 0:
            return []
        if level == 1:
            technicians = [t for t in self._users.list_technicians() if t.is_active]
            technicians.sort(key=lambda t: -t.experience_level)
            return technicians[:1]
        return self._users.list_by_role(Role.ADMIN)

    def sweep(self, incidents: list, *, now: datetime | None = None) -> list[EscalationDecision]:
        decisions = [self.evaluate(i, now=now) for i in incidents]
        return [d for d in decisions if d is not None]
