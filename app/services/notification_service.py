"""Notification delivery, and the two observers that drive it.

The brief asks for at least two mechanisms and says simulation is acceptable.
Three ship here behind one abstract NotificationChannel:

  InAppChannel     writes a row the bell menu reads. Real.
  EmailChannel     simulated. Writes a full RFC style envelope to logs/outbox.
  SmsChannel       simulated. Writes a 160 character message to the same place.

Adding a fourth means writing a class and appending it to the channel list.
NotificationService never names a concrete channel, and neither does anything
above it. Which channels fire is a routing rule based on priority, not an if
statement inside a channel.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import BASE_DIR
from app.domain.enums import EventType, Priority, Role
from app.domain.events import IncidentEvent, Observer
from app.domain.factories import NotificationFactory

logger = logging.getLogger(__name__)

OUTBOX = BASE_DIR / "logs" / "outbox.log"
"""Simulated external sends land here so the demo can show them. A real SMTP or
Twilio adapter would replace the write with a client call and change nothing
else in the system."""


class NotificationChannel(ABC):
    name: str = "channel"
    label: str = ""

    @abstractmethod
    def send(self, user, title: str, message: str, *, incident=None, event_type: str | None = None) -> bool: ...

    def available_for(self, user) -> bool:
        return user is not None and user.is_active

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class InAppChannel(NotificationChannel):
    name = "IN_APP"
    label = "In-app notification"

    def __init__(self, repository) -> None:
        self._repo = repository

    def send(self, user, title, message, *, incident=None, event_type=None) -> bool:
        self._repo.add(
            user_id=user.id,
            incident_id=getattr(incident, "id", None),
            title=title,
            message=message,
            channel=self.name,
            event_type=event_type,
        )
        return True


class _SimulatedChannel(NotificationChannel):
    """Shared behaviour for the two simulated transports."""

    def _write(self, payload: dict) -> bool:
        try:
            OUTBOX.parent.mkdir(parents=True, exist_ok=True)
            with OUTBOX.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, default=str) + "\n")
        except OSError:
            logger.warning("Could not write to the simulated outbox", exc_info=True)
            return False
        logger.info("[%s] to %s :: %s", self.name, payload.get("to"), payload.get("subject"))
        return True


class EmailChannel(_SimulatedChannel):
    name = "EMAIL"
    label = "Email (simulated)"

    def send(self, user, title, message, *, incident=None, event_type=None) -> bool:
        return self._write(
            {
                "channel": self.name,
                "at": datetime.now(timezone.utc),
                "to": user.email,
                "subject": f"[I-ITSM] {title}",
                "body": f"{user.full_name},\n\n{message}\n\n-- \nIT Service Management, BITS Pilani Hyderabad Campus",
                "incident": getattr(incident, "reference", None),
                "event": event_type,
            }
        )


class SmsChannel(_SimulatedChannel):
    name = "SMS"
    label = "SMS (simulated)"

    def send(self, user, title, message, *, incident=None, event_type=None) -> bool:
        body = f"{title}. {message}"
        return self._write(
            {
                "channel": self.name,
                "at": datetime.now(timezone.utc),
                "to": f"+91xxxxx{str(user.employee_code)[-3:]}",
                "text": body[:160],
                "incident": getattr(incident, "reference", None),
                "event": event_type,
            }
        )


class NotificationService:
    """Decides which channels run for a given event, then runs them."""

    URGENT_EVENTS = {EventType.SLA_VIOLATED, EventType.INCIDENT_ESCALATED}

    def __init__(self, channels: list[NotificationChannel]) -> None:
        self._channels = list(channels)

    @property
    def channels(self) -> tuple[NotificationChannel, ...]:
        return tuple(self._channels)

    def register(self, channel: NotificationChannel) -> None:
        self._channels.append(channel)

    def channels_for(self, *, priority: Priority | None, event_type: EventType) -> list[NotificationChannel]:
        """Routing rule. A P1 breach reaches every transport; a P4 comment only
        reaches the bell menu, because nobody should be texted about a P4."""
        urgent = event_type in self.URGENT_EVENTS or (priority is not None and priority.rank == 1)
        if urgent:
            return list(self._channels)
        if priority is not None and priority.rank == 2:
            return [c for c in self._channels if c.name in ("IN_APP", "EMAIL")]
        return [c for c in self._channels if c.name == "IN_APP"]

    def dispatch(self, *, recipients, title: str, message: str, incident=None, event_type: EventType | None = None) -> int:
        priority = getattr(incident, "priority", None)
        channels = self.channels_for(priority=priority, event_type=event_type or EventType.STATUS_CHANGED)
        sent = 0
        for user in recipients:
            if user is None:
                continue
            for channel in channels:
                if not channel.available_for(user):
                    continue
                try:
                    if channel.send(user, title, message, incident=incident, event_type=getattr(event_type, "value", None)):
                        sent += 1
                except Exception:  # a dead transport must not fail the operation
                    logger.exception("Channel %s failed for %s", channel.name, user.employee_code)
        return sent


class NotificationObserver(Observer):
    """Turns domain events into notifications. Subscribed at startup."""

    name = "notifications"

    SUBSCRIBED = {
        EventType.INCIDENT_CREATED,
        EventType.TECHNICIAN_ASSIGNED,
        EventType.INCIDENT_ACKNOWLEDGED,
        EventType.PRIORITY_CHANGED,
        EventType.SLA_APPROACHING,
        EventType.SLA_VIOLATED,
        EventType.INCIDENT_ESCALATED,
        EventType.DUPLICATE_DETECTED,
        EventType.INCIDENT_RESOLVED,
        EventType.INCIDENT_VERIFIED,
        EventType.INCIDENT_CLOSED,
    }

    def __init__(self, notification_service: NotificationService, user_repository) -> None:
        self._notifications = notification_service
        self._users = user_repository

    def handles(self, event_type: EventType) -> bool:
        return event_type in self.SUBSCRIBED

    def _recipients(self, event: IncidentEvent) -> list:
        incident = event.incident
        people: list = []

        def add(user):
            if user is not None and all(user.id != p.id for p in people):
                people.append(user)

        reporter = self._users.get(incident.reporter_id)
        technician = self._users.get(incident.assigned_technician_id) if incident.assigned_technician_id else None

        match event.type:
            case EventType.TECHNICIAN_ASSIGNED:
                add(technician)
            case EventType.SLA_APPROACHING:
                add(technician)
            case EventType.SLA_VIOLATED | EventType.INCIDENT_ESCALATED:
                add(technician)
                for admin in self._users.list_by_role(Role.ADMIN):
                    add(admin)
            case EventType.DUPLICATE_DETECTED:
                add(reporter)
                add(technician)
            case _:
                add(reporter)
                if event.actor_id != getattr(technician, "id", None):
                    add(technician)

        # Never notify the person who just performed the action.
        return [p for p in people if p.id != event.actor_id]

    def notify(self, event: IncidentEvent) -> None:
        built = NotificationFactory.build(event)
        if built is None:
            return
        title, message = built
        self._notifications.dispatch(
            recipients=self._recipients(event),
            title=title,
            message=message,
            incident=event.incident,
            event_type=event.type,
        )


class AuditLogObserver(Observer):
    """Writes the incident history. Subscribed to everything.

    Because this is an observer rather than a call inside each service method,
    the audit trail cannot drift out of step with what actually happened: if an
    event was published, it was logged.
    """

    name = "audit"

    def __init__(self, audit_repository) -> None:
        self._audit = audit_repository

    def notify(self, event: IncidentEvent) -> None:
        incident = event.incident
        self._audit.record(
            actor_id=event.actor_id,
            action=event.type.value,
            entity_type="incident",
            entity_id=getattr(incident, "id", None),
            details={
                "reference": event.reference,
                "description": event.describe(),
                "previous_state": event.payload.get("previous_state"),
                "new_state": event.payload.get("new_state") or getattr(getattr(incident, "status", None), "value", None),
                "actor_name": event.actor_name,
                **{k: v for k, v in event.payload.items() if k not in ("detail", "previous_state", "new_state")},
            },
        )
