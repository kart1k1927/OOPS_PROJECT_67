"""Intelligent features F and G: technician recommendation and suggested
resolutions.

Both answer the same shape of question, "what worked before", from two
different histories: who handled this kind of incident, and what fixed it.

The technician recommender is deliberately separate from AssignmentStrategy.
A strategy decides and the system acts on it; the recommender explains and a
human decides. The admin assign dialog shows a ranked list with reasons.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.intelligence.text import shared_terms, similarity


@dataclass(frozen=True, slots=True)
class TechnicianRecommendation:
    technician: object
    score: float
    reasons: list[str]

    @property
    def percent(self) -> int:
        return int(round(self.score * 100))


@dataclass(frozen=True, slots=True)
class ResolutionSuggestion:
    incident: object
    score: float
    resolution: str
    shared: list[str]

    @property
    def reference(self) -> str:
        return self.incident.reference


class TechnicianRecommender:
    """Ranks technicians on skills, spare capacity, experience and track
    record with the affected service."""

    WEIGHTS = {"skill": 0.40, "capacity": 0.25, "experience": 0.20, "history": 0.15}

    def __init__(self, incident_repository) -> None:
        self._repo = incident_repository

    def _history_score(self, technician, incident) -> tuple[float, int]:
        if incident.service is None:
            return 0.0, 0
        handled = [
            i
            for i in self._repo.resolved_with_notes(None, limit=200)
            if i.assigned_technician_id == technician.id and i.service and i.service.id == incident.service.id
        ]
        return min(len(handled) / 5.0, 1.0), len(handled)

    def rank(self, incident, technicians: list, *, limit: int = 5) -> list[TechnicianRecommendation]:
        out: list[TechnicianRecommendation] = []
        for technician in technicians:
            if not technician.is_active:
                continue

            reasons: list[str] = []
            category_id = incident.category.id if incident.category else None
            skill = 1.0 if technician.knows(category_id) else 0.0
            if skill:
                reasons.append(f"trained in {incident.category.name}")

            capacity = max(0.0, 1.0 - technician.load_fraction)
            if technician.has_capacity:
                reasons.append(f"{technician.spare_capacity} of {technician.max_workload} slots free")
            else:
                reasons.append("at workload limit")

            experience = (technician.experience_level - 1) / 4.0
            if technician.experience_level >= 4:
                reasons.append(f"experience level {technician.experience_level} of 5")

            history, handled = self._history_score(technician, incident)
            if handled:
                reasons.append(f"has resolved {handled} on {incident.service.name}")

            score = (
                self.WEIGHTS["skill"] * skill
                + self.WEIGHTS["capacity"] * capacity
                + self.WEIGHTS["experience"] * experience
                + self.WEIGHTS["history"] * history
            )
            if not technician.has_capacity:
                score *= 0.5  # still shown, but never top of the list

            out.append(TechnicianRecommendation(technician, round(score, 3), reasons))

        out.sort(key=lambda r: -r.score)
        return out[:limit]


class ResolutionRecommender:
    """Suggests resolutions that worked on similar incidents before."""

    THRESHOLD = 0.25

    def __init__(self, incident_repository) -> None:
        self._repo = incident_repository

    def suggest(self, incident, *, limit: int = 3) -> list[ResolutionSuggestion]:
        category_id = incident.category.id if incident.category else None
        history = self._repo.resolved_with_notes(category_id, limit=60)
        text = f"{incident.title} {incident.description or ''}"

        found: list[ResolutionSuggestion] = []
        for past in history:
            if past.id == incident.id or not past.resolution_notes:
                continue
            score = similarity(text, f"{past.title} {past.description or ''}")
            if past.service and incident.service and past.service.id == incident.service.id:
                score += 0.10
            if score >= self.THRESHOLD:
                found.append(
                    ResolutionSuggestion(
                        past,
                        round(min(score, 1.0), 3),
                        past.resolution_notes,
                        shared_terms(text, past.title),
                    )
                )

        found.sort(key=lambda s: -s.score)
        return found[:limit]
