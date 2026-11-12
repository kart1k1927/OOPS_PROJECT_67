"""The configurable catalogue: IT services, incident categories, SLA policies.

These are aggregated by an Incident, not owned by it. Deleting an incident must
not delete the Payment Application service, which is why these are separate
objects referenced by id rather than values copied into the incident row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from app.core.exceptions import ValidationError
from app.domain.enums import Priority


@dataclass(frozen=True, slots=True)
class Category:
    id: UUID
    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ITService:
    id: UUID
    name: str
    business_criticality: int
    description: str | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.business_criticality <= 5:
            raise ValidationError(
                f"Business criticality for {self.name} must be between 1 and 5.",
                field="business_criticality",
            )


@dataclass(frozen=True, slots=True)
class SLAPolicy:
    """Response, resolution and escalation targets for one priority.

    Stored in hours as a decimal so that P1's five minute response target is
    0.0833 rather than a second unit column.
    """

    priority: Priority
    response_hours: float
    resolution_hours: float
    escalation_hours: float
    id: UUID | None = None

    @property
    def response_target(self) -> timedelta:
        return timedelta(hours=float(self.response_hours))

    @property
    def resolution_target(self) -> timedelta:
        return timedelta(hours=float(self.resolution_hours))

    @property
    def escalation_target(self) -> timedelta:
        return timedelta(hours=float(self.escalation_hours))

    def describe(self) -> str:
        def human(hours: float) -> str:
            minutes = round(float(hours) * 60)
            if minutes < 60:
                return f"{minutes}m"
            if minutes % 60 == 0:
                return f"{minutes // 60}h"
            return f"{minutes // 60}h {minutes % 60}m"

        return f"respond in {human(self.response_hours)}, resolve in {human(self.resolution_hours)}"


@dataclass(frozen=True, slots=True)
class TechnicianSkill:
    technician_id: UUID
    category_id: UUID
    category_name: str = ""
