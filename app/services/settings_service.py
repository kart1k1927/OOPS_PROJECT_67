"""Runtime configuration an administrator can change without a restart.

This is what makes "the assignment strategy can be changed without redesigning
the application" demonstrable rather than theoretical: the admin settings screen
posts a strategy name here, and the very next incident is assigned by the new
one.
"""

from __future__ import annotations

from app.domain.assignment import (
    ASSIGNMENT_STRATEGIES,
    DEFAULT_ASSIGNMENT_STRATEGY,
    AssignmentStrategy,
    get_assignment_strategy,
)
from app.domain.priority import (
    DEFAULT_PRIORITY_STRATEGY,
    PRIORITY_STRATEGIES,
    PriorityStrategy,
    get_priority_strategy,
)


class SystemSettings:
    def __init__(self) -> None:
        self._assignment_name = DEFAULT_ASSIGNMENT_STRATEGY
        self._priority_name = DEFAULT_PRIORITY_STRATEGY
        self._auto_assign = True
        self._duplicate_detection = True
        self._auto_categorize = True

    @property
    def assignment_strategy(self) -> AssignmentStrategy:
        return get_assignment_strategy(self._assignment_name)

    @property
    def assignment_strategy_name(self) -> str:
        return self._assignment_name

    def set_assignment_strategy(self, name: str) -> None:
        if name not in ASSIGNMENT_STRATEGIES:
            raise KeyError(name)
        self._assignment_name = name

    @property
    def priority_strategy(self) -> PriorityStrategy:
        return get_priority_strategy(self._priority_name)

    @property
    def priority_strategy_name(self) -> str:
        return self._priority_name

    def set_priority_strategy(self, name: str) -> None:
        if name not in PRIORITY_STRATEGIES:
            raise KeyError(name)
        self._priority_name = name

    @property
    def auto_assign(self) -> bool:
        return self._auto_assign

    @property
    def duplicate_detection(self) -> bool:
        return self._duplicate_detection

    @property
    def auto_categorize(self) -> bool:
        return self._auto_categorize

    def toggle(self, key: str, value: bool) -> None:
        if key not in ("auto_assign", "duplicate_detection", "auto_categorize"):
            raise KeyError(key)
        setattr(self, f"_{key}", bool(value))

    def as_dict(self) -> dict:
        return {
            "assignment_strategy": self._assignment_name,
            "priority_strategy": self._priority_name,
            "auto_assign": self._auto_assign,
            "duplicate_detection": self._duplicate_detection,
            "auto_categorize": self._auto_categorize,
        }
