"""Composition root.

The one place that names concrete classes. Everything else receives what it
needs through its constructor, which is what makes the in-memory test container
possible: build_test_container() swaps five classes and changes nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.events import EventBus
from app.services.auth_service import AuthService
from app.services.incident_service import IncidentService
from app.services.intelligence.categorizer import IncidentCategorizer
from app.services.intelligence.duplicate_detector import DuplicateDetector
from app.services.intelligence.escalation_engine import EscalationEngine
from app.services.intelligence.recommender import ResolutionRecommender, TechnicianRecommender
from app.services.intelligence.sla_risk import SLARiskDetector
from app.services.notification_service import (
    AuditLogObserver,
    EmailChannel,
    InAppChannel,
    NotificationObserver,
    NotificationService,
    SmsChannel,
)
from app.services.reporting_service import ReportingService
from app.services.settings_service import SystemSettings
from app.services.sla_service import SLAService


@dataclass(slots=True)
class Container:
    catalog: object
    users: object
    incidents: object
    audit: object
    notifications: object
    bus: EventBus
    settings: SystemSettings
    auth: AuthService
    incident_service: IncidentService
    notification_service: NotificationService
    sla_service: SLAService
    reporting: ReportingService
    risk: SLARiskDetector
    escalation: EscalationEngine


def _assemble(*, catalog, users, incidents, audit, notifications) -> Container:
    users.bind_incidents(incidents)

    bus = EventBus()
    settings = SystemSettings()

    notification_service = NotificationService([InAppChannel(notifications), EmailChannel(), SmsChannel()])
    bus.subscribe(AuditLogObserver(audit))
    bus.subscribe(NotificationObserver(notification_service, users))

    escalation = EscalationEngine(users)
    risk = SLARiskDetector(workload_lookup=lambda tid: incidents.active_workload().get(tid, 0))

    incident_service = IncidentService(
        incidents=incidents,
        users=users,
        catalog=catalog,
        event_bus=bus,
        settings=settings,
        duplicate_detector=DuplicateDetector(incidents),
        categorizer=IncidentCategorizer(),
        technician_recommender=TechnicianRecommender(incidents),
        resolution_recommender=ResolutionRecommender(incidents),
    )

    return Container(
        catalog=catalog,
        users=users,
        incidents=incidents,
        audit=audit,
        notifications=notifications,
        bus=bus,
        settings=settings,
        auth=AuthService(users, audit),
        incident_service=incident_service,
        notification_service=notification_service,
        sla_service=SLAService(incidents, catalog, bus, escalation),
        reporting=ReportingService(incidents, users, catalog, risk),
        risk=risk,
        escalation=escalation,
    )


def build_container(client=None) -> Container:
    """Production wiring, against Supabase.

    Pass a client to build a second, independent graph: the SLA monitor uses
    one so its connection pool is separate from the one serving requests.
    """
    from app.database.database import get_client
    from app.repositories.supabase_repo import (
        SupabaseAuditRepository,
        SupabaseCatalogRepository,
        SupabaseIncidentRepository,
        SupabaseNotificationRepository,
        SupabaseUserRepository,
    )

    client = client or get_client()
    catalog = SupabaseCatalogRepository(client)
    incidents = SupabaseIncidentRepository(client, catalog)
    return _assemble(
        catalog=catalog,
        users=SupabaseUserRepository(client, incidents),
        incidents=incidents,
        audit=SupabaseAuditRepository(client),
        notifications=SupabaseNotificationRepository(client),
    )


def build_test_container(*, services=(), categories=(), policies=(), users=()) -> Container:
    """In-memory wiring, for the test suite. No network, no keys."""
    from app.repositories.memory_repo import (
        InMemoryAuditRepository,
        InMemoryCatalogRepository,
        InMemoryIncidentRepository,
        InMemoryNotificationRepository,
        InMemoryUserRepository,
    )

    incidents = InMemoryIncidentRepository()
    return _assemble(
        catalog=InMemoryCatalogRepository(services=services, categories=categories, policies=policies),
        users=InMemoryUserRepository(users, incidents),
        incidents=incidents,
        audit=InMemoryAuditRepository(),
        notifications=InMemoryNotificationRepository(),
    )
