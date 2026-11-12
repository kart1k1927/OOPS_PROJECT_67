"""Dashboards and analytics.

Read only aggregation for the administrator screens. Kept out of
IncidentService because reporting has no business rules, it only counts.
"""

from __future__ import annotations

from app.domain.enums import Priority, Role, SLAState, Status
from app.repositories.base import IncidentQuery


class ReportingService:
    def __init__(self, incidents, users, catalog, risk_detector=None) -> None:
        self._incidents = incidents
        self._users = users
        self._catalog = catalog
        self._risk = risk_detector

    def overview(self) -> dict:
        tally = self._incidents.status_tally()
        total = sum(tally.values())
        resolved = tally.get(Status.RESOLVED.value, 0) + tally.get(Status.VERIFIED.value, 0) + tally.get(Status.CLOSED.value, 0)
        open_count = sum(v for k, v in tally.items() if Status(k).is_open)

        open_incidents = self._incidents.open_incidents()
        critical = len([i for i in open_incidents if i.priority is Priority.P1])
        breached = len([i for i in open_incidents if i.sla.resolution_breached or i.sla.response_breached])

        return {
            "total": total,
            "open": open_count,
            "critical_open": critical,
            "resolved": resolved,
            "sla_violations": breached,
            "by_status": tally,
        }

    def technician_workload(self) -> list[dict]:
        out = []
        for technician in self._users.list_technicians():
            out.append(
                {
                    "technician": technician,
                    "active": technician.active_workload,
                    "capacity": technician.max_workload,
                    "resolved": technician.resolved_count,
                    "skills": technician.skill_names,
                    "experience": technician.experience_level,
                    "load_percent": int(technician.load_fraction * 100),
                }
            )
        out.sort(key=lambda row: -row["active"])
        return out

    def service_analysis(self) -> list[dict]:
        tally = self._incidents.service_tally()
        return [
            {"service": name, "total": data["total"], "open": data["open"], "criticality": data["criticality"]}
            for name, data in tally.items()
        ]

    def category_analysis(self) -> list[dict]:
        tally = self._incidents.category_tally()
        total = sum(tally.values()) or 1
        return [
            {"category": name, "count": count, "percent": round(count * 100 / total)}
            for name, count in tally.items()
        ]

    def sla_breaches(self, *, limit: int = 20) -> list:
        open_incidents = self._incidents.open_incidents()
        breached = [i for i in open_incidents if i.sla_state is SLAState.BREACHED]
        breached.sort(key=lambda i: i.priority.rank)
        return breached[:limit]

    def at_risk(self, *, limit: int = 10) -> list:
        if self._risk is None:
            return []
        return self._risk.at_risk(self._incidents.open_incidents())[:limit]

    def priority_mix(self) -> list[dict]:
        incidents = self._incidents.search(IncidentQuery(limit=1000))
        tally: dict[str, int] = {}
        for incident in incidents:
            tally[incident.priority.value] = tally.get(incident.priority.value, 0) + 1
        total = sum(tally.values()) or 1
        return [
            {"priority": p.value, "label": p.label, "count": tally.get(p.value, 0), "percent": round(tally.get(p.value, 0) * 100 / total)}
            for p in Priority
        ]

    def feedback_summary(self) -> dict:
        incidents = self._incidents.search(IncidentQuery(limit=1000))
        rated = [i for i in incidents if i.feedback_rating]
        if not rated:
            return {"count": 0, "average": None}
        return {
            "count": len(rated),
            "average": round(sum(i.feedback_rating for i in rated) / len(rated), 2),
        }
