"""An action a particular user may take on a particular incident right now.

The UI renders buttons straight from a list of these, which is why the
technician work view shows fewer buttons rather than disabled ones: if the
state machine does not permit it and the role does not own it, no Action is
produced and no button exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import Status


@dataclass(frozen=True, slots=True)
class Action:
    key: str
    label: str
    target_status: Status | None = None
    style: str = "secondary"  # secondary | primary | danger
    needs_note: bool = False

    def __str__(self) -> str:
        return self.label
