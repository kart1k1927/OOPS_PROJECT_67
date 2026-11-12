"""Strategy pattern for technician assignment.

The brief asks for at least two strategies and for the strategy to be
changeable without redesigning the application. Four ship here, selected by
name from the admin settings screen at runtime. IncidentService holds a
reference to the abstract type and never names a concrete one, so adding a
fifth means writing a class and registering it.

Every strategy filters on availability first: inactive technicians and
technicians already at their workload ceiling are never selected, whatever the
ranking rule says.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import count

from app.core.exceptions import TechnicianUnavailableError
from app.domain.enums import Priority


@dataclass(frozen=True, slots=True)
class AssignmentDecision:
    technician: object
    reason: str
    strategy: str


class AssignmentStrategy(ABC):
    name: str = "assignment"
    label: str = ""
    description: str = ""

    @abstractmethod
    def _rank(self, incident, candidates: list) -> list: ...

    def available(self, incident, technicians: list) -> list:
        return [t for t in technicians if t.is_available_for(incident)]

    def select(self, incident, technicians: list) -> AssignmentDecision:
        candidates = self.available(incident, technicians)
        if not candidates:
            if not technicians:
                raise TechnicianUnavailableError("No technicians are registered. An administrator must add one.")
            raise TechnicianUnavailableError(
                "Every technician is inactive or at their workload limit. Raise a limit or activate another technician."
            )
        ranked = self._rank(incident, candidates)
        if not ranked:
            raise TechnicianUnavailableError(
                f"No technician matches this incident under the {self.label} strategy."
            )
        chosen = ranked[0]
        return AssignmentDecision(chosen, self.reason_for(incident, chosen), self.name)

    def reason_for(self, incident, technician) -> str:
        return f"{self.label}: {technician.full_name} carrying {technician.active_workload} of {technician.max_workload}"

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class SkillBasedAssignment(AssignmentStrategy):
    name = "skill"
    label = "Skill based"
    description = "Prefers a technician trained in the incident's category. Falls back to the least loaded if nobody is."

    def _rank(self, incident, candidates: list) -> list:
        category_id = incident.category.id if incident.category else None
        skilled = [t for t in candidates if t.knows(category_id)]
        pool = skilled or candidates
        return sorted(pool, key=lambda t: (t.active_workload, -t.experience_level, t.employee_code))

    def reason_for(self, incident, technician) -> str:
        category = incident.category.name if incident.category else "uncategorised"
        if incident.category and technician.knows(incident.category.id):
            return f"Skill based: {technician.full_name} is trained in {category} and is carrying {technician.active_workload}"
        return f"Skill based: nobody is trained in {category}, fell back to the least loaded technician"


class LoadBalancedAssignment(AssignmentStrategy):
    name = "load"
    label = "Load balanced"
    description = "Always picks the technician with the fewest active incidents. Ties break on experience."

    def _rank(self, incident, candidates: list) -> list:
        return sorted(candidates, key=lambda t: (t.load_fraction, t.active_workload, -t.experience_level, t.employee_code))


class RoundRobinAssignment(AssignmentStrategy):
    name = "round_robin"
    label = "Round robin"
    description = "Hands incidents out in turn, ignoring skills and load. Useful as a fairness baseline."

    def __init__(self) -> None:
        self._counter = count()

    def _rank(self, incident, candidates: list) -> list:
        ordered = sorted(candidates, key=lambda t: t.employee_code)
        offset = next(self._counter) % len(ordered)
        return ordered[offset:] + ordered[:offset]

    def reason_for(self, incident, technician) -> str:
        return f"Round robin: {technician.full_name} was next in rotation"


class ExperienceBasedAssignment(AssignmentStrategy):
    name = "experience"
    label = "Experience weighted"
    description = "Sends P1 and P2 incidents to the most experienced technician, everything else to the least loaded."

    def _rank(self, incident, candidates: list) -> list:
        if incident.priority.rank <= 2:
            return sorted(candidates, key=lambda t: (-t.experience_level, t.active_workload, t.employee_code))
        return sorted(candidates, key=lambda t: (t.active_workload, -t.experience_level, t.employee_code))

    def reason_for(self, incident, technician) -> str:
        if incident.priority.rank <= 2:
            return (
                f"Experience weighted: {incident.priority.value} went to {technician.full_name}, "
                f"level {technician.experience_level} of 5"
            )
        return f"Experience weighted: {incident.priority.value} went to the least loaded, {technician.full_name}"


ASSIGNMENT_STRATEGIES: dict[str, AssignmentStrategy] = {
    s.name: s
    for s in (SkillBasedAssignment(), LoadBalancedAssignment(), RoundRobinAssignment(), ExperienceBasedAssignment())
}
DEFAULT_ASSIGNMENT_STRATEGY = "skill"


def get_assignment_strategy(name: str | None = None) -> AssignmentStrategy:
    return ASSIGNMENT_STRATEGIES.get(name or DEFAULT_ASSIGNMENT_STRATEGY, ASSIGNMENT_STRATEGIES[DEFAULT_ASSIGNMENT_STRATEGY])


def describe_strategies() -> list[dict]:
    return [
        {"name": s.name, "label": s.label, "description": s.description}
        for s in ASSIGNMENT_STRATEGIES.values()
    ]
