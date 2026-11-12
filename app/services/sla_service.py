"""SLA monitoring.

The original schema shipped refresh_incident_sla_breaches() but nothing ever
called it, so every breach flag in the database stayed false forever. This
replaces it in Python and is driven by a FastAPI background task started at
application startup, so monitoring is continuous rather than aspirational.

The sweep does three things on every pass: refresh the breach flags, warn once
when an incident crosses the risk threshold, and hand anything overdue to the
escalation engine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.domain.enums import EventType, Priority
from app.domain.events import IncidentEvent
from app.domain.sla import AT_RISK_FRACTION

logger = logging.getLogger(__name__)


def human_duration(delta) -> str:
    """2h 14m. Negative renders as -0h 42m, which is how the UI shows an
    incident that is already late."""
    if delta is None:
        return "no deadline"
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    hours, minutes = divmod(total // 60, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{sign}{days}d {hours}h"
    return f"{sign}{hours}h {minutes}m"


class SLAService:
    def __init__(self, incident_repository, catalog_repository, event_bus, escalation_engine=None) -> None:
        self._incidents = incident_repository
        self._catalog = catalog_repository
        self._bus = event_bus
        self._escalation = escalation_engine
        self._warned: set = set()

    def policy_for(self, priority: Priority):
        return self._catalog.get_sla_policy(priority)

    def sweep(self, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        open_incidents = self._incidents.open_incidents()

        breached, warned, escalated = 0, 0, 0

        for incident in open_incidents:
            changed = incident.refresh_sla(now=now)

            if incident.sla.resolution_breached:
                if changed:
                    self._incidents.update(incident)
                    breached += 1
                    self._bus.publish(
                        IncidentEvent(
                            EventType.SLA_VIOLATED,
                            incident,
                            None,
                            {
                                "detail": (
                                    f"{incident.reference} breached its {incident.priority.value} resolution "
                                    f"target of {human_duration(incident.sla.policy.resolution_target) if incident.sla.policy else 'unknown'}."
                                )
                            },
                        )
                    )
            elif changed:
                self._incidents.update(incident)

            # Warn once per incident, when it crosses the risk line.
            fraction = incident.sla.elapsed_fraction(now=now)
            if (
                not incident.sla.resolution_breached
                and fraction >= AT_RISK_FRACTION
                and incident.id not in self._warned
            ):
                self._warned.add(incident.id)
                warned += 1
                remaining = human_duration(incident.sla.resolution_remaining(now=now))
                self._bus.publish(
                    IncidentEvent(
                        EventType.SLA_APPROACHING,
                        incident,
                        None,
                        {
                            "detail": f"{incident.reference} is {int(fraction * 100)} percent through its SLA window, {remaining} left.",
                            "remaining": remaining,
                        },
                    )
                )

            if self._escalation is not None:
                decision = self._escalation.evaluate(incident, now=now)
                if decision is not None:
                    incident.escalate(decision.to_level, reason=decision.reason)
                    self._incidents.update(incident)
                    escalated += 1
                    self._bus.publish(
                        IncidentEvent(
                            EventType.INCIDENT_ESCALATED,
                            incident,
                            None,
                            {
                                "detail": (
                                    f"{incident.reference} escalated to {decision.tier_name} "
                                    f"(level {decision.to_level}). {decision.reason}"
                                ),
                                "level": decision.to_level,
                            },
                        )
                    )

        result = {
            "checked": len(open_incidents),
            "breached": breached,
            "warned": warned,
            "escalated": escalated,
            "at": now,
        }
        if breached or warned or escalated:
            logger.info("SLA sweep %s", result)
        return result
