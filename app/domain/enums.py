"""Value types for the incident domain.

Every one of these is a closed set with behaviour attached. Using str Enum
rather than bare strings means an invalid priority cannot exist in the system:
it fails at construction, not three layers later at the database.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    TECHNICIAN = "TECHNICIAN"
    ADMIN = "ADMIN"

    @property
    def label(self) -> str:
        return {"EMPLOYEE": "Employee", "TECHNICIAN": "Technician", "ADMIN": "Administrator"}[self.value]


class Status(str, Enum):
    OPEN = "OPEN"
    CLASSIFIED = "CLASSIFIED"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()

    @property
    def is_terminal(self) -> bool:
        return self is Status.CLOSED

    @property
    def is_open(self) -> bool:
        """Counts towards a technician's active workload."""
        return self in _ACTIVE_STATUSES


_ACTIVE_STATUSES = frozenset(
    {Status.OPEN, Status.CLASSIFIED, Status.ASSIGNED, Status.ACKNOWLEDGED, Status.IN_PROGRESS, Status.PENDING}
)


class Impact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def weight(self) -> int:
        return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}[self.value]


class Urgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def weight(self) -> int:
        return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}[self.value]


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @property
    def label(self) -> str:
        return {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}[self.value]

    @property
    def rank(self) -> int:
        """1 is the most urgent. Use for sorting a queue."""
        return int(self.value[1])

    def __lt__(self, other: object) -> bool:  # queue ordering, P1 first
        if not isinstance(other, Priority):
            return NotImplemented
        return self.rank < other.rank


class UpdateType(str, Enum):
    COMMENT = "COMMENT"
    STATUS_CHANGE = "STATUS_CHANGE"
    ASSIGNMENT = "ASSIGNMENT"
    SYSTEM = "SYSTEM"


class EventType(str, Enum):
    """What the observers listen for."""

    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_CLASSIFIED = "INCIDENT_CLASSIFIED"
    PRIORITY_CALCULATED = "PRIORITY_CALCULATED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    TECHNICIAN_ASSIGNED = "TECHNICIAN_ASSIGNED"
    INCIDENT_ACKNOWLEDGED = "INCIDENT_ACKNOWLEDGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    NOTE_ADDED = "NOTE_ADDED"
    SLA_APPROACHING = "SLA_APPROACHING"
    SLA_VIOLATED = "SLA_VIOLATED"
    INCIDENT_ESCALATED = "INCIDENT_ESCALATED"
    DUPLICATE_DETECTED = "DUPLICATE_DETECTED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    INCIDENT_VERIFIED = "INCIDENT_VERIFIED"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"
    FEEDBACK_RECEIVED = "FEEDBACK_RECEIVED"


class SLAState(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"
    MET = "MET"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()
