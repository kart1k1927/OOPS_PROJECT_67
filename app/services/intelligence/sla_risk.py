"""Intelligent feature E: SLA risk detection.

Predicts which open incidents are going to miss their resolution target, before
they do. No model, five weighted signals:

  how far through the window the incident is
  whether anyone has responded yet
  how loaded the assigned technician is
  whether it is still sitting unacknowledged
  how severe it is

Each contributes to a 0 to 100 score with a sentence attached, so the admin
screen can say why an incident is at risk rather than showing a number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.enums import SLAState, Status


@dataclass(slots=True)
class RiskAssessment:
    incident: object
    score: int
    signals: list[str] = field(default_factory=list)

    @property
    def band(self) -> str:
        if self.score >= 70:
            return "HIGH"
        if self.score >= 40:
            return "MEDIUM"
        return "LOW"

    @property
    def reference(self) -> str:
        return self.incident.reference

    def explain(self) -> str:
        return "; ".join(self.signals) if self.signals else "No risk signals."


class SLARiskDetector:
    def __init__(self, workload_lookup=None) -> None:
        self._workload = workload_lookup or (lambda _: 0)

    def assess(self, incident, *, now: datetime | None = None) -> RiskAssessment:
        now = now or datetime.now(timezone.utc)
        score = 0
        signals: list[str] = []

        if not incident.is_open:
            return RiskAssessment(incident, 0, ["Already resolved or closed."])

        if incident.sla_state is SLAState.BREACHED:
            return RiskAssessment(incident, 100, ["Resolution deadline has already passed."])

        elapsed = incident.sla.elapsed_fraction(now=now)
        if elapsed >= 0.9:
            score += 45
            signals.append(f"{int(elapsed * 100)} percent of the resolution window has gone")
        elif elapsed >= 0.75:
            score += 30
            signals.append(f"{int(elapsed * 100)} percent of the resolution window has gone")
        elif elapsed >= 0.5:
            score += 15
            signals.append("past halfway through the resolution window")

        if incident.first_response_at is None:
            score += 20
            signals.append("nobody has responded yet")

        if incident.status in (Status.OPEN, Status.CLASSIFIED, Status.ASSIGNED):
            score += 15
            signals.append(f"still {incident.status.label.lower()}")
        elif incident.status is Status.PENDING:
            score += 10
            signals.append("waiting on the reporter")

        if incident.assigned_technician_id:
            load = self._workload(incident.assigned_technician_id)
            if load >= 5:
                score += 15
                signals.append(f"assigned technician is carrying {load} incidents")
            elif load >= 3:
                score += 8
                signals.append(f"assigned technician is carrying {load} incidents")
        else:
            score += 12
            signals.append("not assigned to anyone")

        if incident.priority.rank == 1:
            score += 10
            signals.append("critical priority")
        elif incident.priority.rank == 2:
            score += 5

        return RiskAssessment(incident, min(score, 100), signals)

    def at_risk(self, incidents: list, *, threshold: int = 40, now: datetime | None = None) -> list[RiskAssessment]:
        found = [self.assess(i, now=now) for i in incidents]
        found = [a for a in found if a.score >= threshold]
        found.sort(key=lambda a: (-a.score, a.incident.priority.rank))
        return found
