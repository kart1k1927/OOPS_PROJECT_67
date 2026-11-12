"""Intelligent feature A: duplicate and related incident detection.

Three reports of the same outage look like this:

    INC101  Payment application unavailable
    INC102  Payment transaction failing
    INC103  Unable to make payment

They share a service and a vocabulary within a short window. The detector
scores every recent incident on the same service against the new one and
returns anything over the threshold, ranked. It never blocks a submission: the
reporter sees the matches above the submit button and decides, because a
helpdesk that refuses reports is worse than one with duplicates in it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.intelligence.text import shared_terms, similarity


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    incident: object
    score: float
    shared: list[str]

    @property
    def reference(self) -> str:
        return self.incident.reference

    def explain(self) -> str:
        terms = ", ".join(self.shared) if self.shared else "the same service"
        return f"{self.reference} is {int(self.score * 100)} percent similar, both mention {terms}"


class DuplicateDetector:
    THRESHOLD = 0.30
    SAME_SERVICE_BONUS = 0.14
    SAME_CATEGORY_BONUS = 0.06
    WINDOW_HOURS = 48

    def __init__(self, incident_repository, *, threshold: float | None = None, window_hours: int | None = None) -> None:
        self._repo = incident_repository
        self._threshold = threshold if threshold is not None else self.THRESHOLD
        self._window = window_hours or self.WINDOW_HOURS

    def _text(self, incident) -> str:
        return f"{incident.title} {incident.description or ''}"

    def score(self, candidate, against) -> float:
        base = similarity(self._text(candidate), self._text(against))
        if candidate.service and against.service and candidate.service.id == against.service.id:
            base += self.SAME_SERVICE_BONUS
        if candidate.category and against.category and candidate.category.id == against.category.id:
            base += self.SAME_CATEGORY_BONUS
        return round(min(base, 1.0), 3)

    def find(self, incident, *, limit: int = 3) -> list[DuplicateMatch]:
        service_id = incident.service.id if incident.service else None
        recent = self._repo.recent_for_service(service_id, within_hours=self._window, exclude_id=incident.id)

        matches: list[DuplicateMatch] = []
        for other in recent:
            if other.status.is_terminal:
                continue
            value = self.score(incident, other)
            if value >= self._threshold:
                matches.append(DuplicateMatch(other, value, shared_terms(self._text(incident), self._text(other))))

        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[:limit]

    def correlate(self, incidents: list, *, min_cluster: int = 2) -> list[dict]:
        """Intelligent feature B: incident correlation.

        Groups currently open incidents by the service they affect, so an
        administrator sees "Payment Application has 6 open incidents" rather
        than six separate rows. A cluster on one service inside a short window
        is usually one underlying fault.
        """
        clusters: dict[str, list] = {}
        for incident in incidents:
            if incident.service is None:
                continue
            clusters.setdefault(incident.service.name, []).append(incident)

        out = []
        for name, group in clusters.items():
            if len(group) < min_cluster:
                continue
            group.sort(key=lambda i: i.created_at)
            out.append(
                {
                    "service": name,
                    "count": len(group),
                    "criticality": group[0].business_criticality,
                    "incidents": group,
                    "worst_priority": min(i.priority for i in group),
                    "first_seen": group[0].created_at,
                }
            )
        out.sort(key=lambda c: (-c["count"], c["worst_priority"].rank))
        return out
