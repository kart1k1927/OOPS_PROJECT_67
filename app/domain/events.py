"""Observer pattern.

An incident does not know that notifications or an audit trail exist. It raises
an event; whoever subscribed reacts. That is what lets the audit trail be
complete without every service method remembering to write a log line, and it
is why adding a third listener (a metrics collector, a Slack relay) touches no
existing code.

One deliberate decision: an observer that raises is logged and skipped, never
allowed to propagate. A failure to send an email must not roll back the
incident that was successfully created.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.domain.enums import EventType

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IncidentEvent:
    type: EventType
    incident: Any
    actor: Any = None
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def actor_name(self) -> str:
        return getattr(self.actor, "full_name", "System")

    @property
    def actor_id(self):
        return getattr(self.actor, "id", None)

    @property
    def reference(self) -> str:
        return getattr(self.incident, "reference", "")

    def describe(self) -> str:
        """The audit line. Mirrors the format in the problem statement."""
        detail = self.payload.get("detail")
        if detail:
            return detail
        return self.type.value.replace("_", " ").capitalize()


class Observer(ABC):
    """A listener. Declares which events it cares about."""

    name: str = "observer"

    def handles(self, event_type: EventType) -> bool:
        return True

    @abstractmethod
    def notify(self, event: IncidentEvent) -> None: ...


class EventBus:
    """The Subject half of the pattern."""

    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def subscribe(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    @property
    def observers(self) -> tuple[Observer, ...]:
        return tuple(self._observers)

    def publish(self, event: IncidentEvent) -> None:
        for observer in self._observers:
            if not observer.handles(event.type):
                continue
            try:
                observer.notify(event)
            except Exception:  # one broken listener must not fail the operation
                logger.exception("Observer %s failed handling %s", observer.name, event.type.value)

    def publish_many(self, events: list[IncidentEvent]) -> None:
        for event in events:
            self.publish(event)
