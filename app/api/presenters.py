"""View helpers shared by the templates.

Formatting lives here rather than in Jinja, so the "time is absolute with
relative as secondary" rule from docs/design-system.md is implemented once.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import Priority, SLAState, Status

PRIORITY_CLASS = {Priority.P1: "p1", Priority.P2: "p2", Priority.P3: "p3", Priority.P4: "p4"}

STATUS_CLASS = {
    Status.OPEN: "open",
    Status.CLASSIFIED: "open",
    Status.ASSIGNED: "open",
    Status.ACKNOWLEDGED: "open",
    Status.IN_PROGRESS: "open",
    Status.PENDING: "hold",
    Status.RESOLVED: "ok",
    Status.VERIFIED: "ok",
    Status.CLOSED: "done",
}

SLA_CLASS = {
    SLAState.ON_TRACK: "ok",
    SLAState.MET: "ok",
    SLAState.AT_RISK: "risk",
    SLAState.BREACHED: "late",
    SLAState.NOT_APPLICABLE: "none",
}


def absolute(value: datetime | None) -> str:
    if value is None:
        return "not set"
    return value.astimezone().strftime("%H:%M, %d %b")


def relative(value: datetime | None) -> str:
    if value is None:
        return ""
    seconds = int((datetime.now(timezone.utc) - value).total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


def duration(delta) -> str:
    from app.services.sla_service import human_duration

    return human_duration(delta)


def sla_percent(incident) -> int:
    return min(int(incident.sla.elapsed_fraction(resolved_at=incident.resolved_at) * 100), 100)


def sla_remaining(incident) -> str:
    if incident.resolved_at:
        return "resolved"
    return duration(incident.sla.resolution_remaining())


def register(templates) -> None:
    env = templates.env
    env.filters["absolute"] = absolute
    env.filters["relative"] = relative
    env.filters["duration"] = duration
    env.globals.update(
        priority_class=lambda p: PRIORITY_CLASS.get(p, "p4"),
        status_class=lambda s: STATUS_CLASS.get(s, "open"),
        sla_class=lambda s: SLA_CLASS.get(s, "none"),
        sla_percent=sla_percent,
        sla_remaining=sla_remaining,
        now=lambda: datetime.now(timezone.utc),
    )
