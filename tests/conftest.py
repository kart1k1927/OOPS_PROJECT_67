"""Test fixtures.

Everything runs against the in-memory repositories, so the suite needs no
database, no keys and no network. That is the practical argument for the
Repository pattern, and it is why these tests exercise the real domain logic
rather than mocks of it.

The environment defaults below exist because app/main.py validates settings at
import time, and the HTTP tests import it. They never reach Supabase: those
tests swap in the in-memory container before the first request. Without these
a freshly cloned checkout cannot run the suite until somebody fills in .env,
which defeats the point of a suite that needs no infrastructure.
"""

from __future__ import annotations

import os

# Must happen before anything under app/ is imported.
os.environ.setdefault("SUPABASE_URL", "https://tests.invalid")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-outside-the-suite")

from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.domain.catalog import Category, ITService, SLAPolicy
from app.domain.enums import Priority, Role
from app.domain.factories import UserFactory
from app.services.container import build_test_container

PASSWORD = "campus2026"


@pytest.fixture
def categories():
    return {
        "application": Category(id=uuid4(), name="Application"),
        "network": Category(id=uuid4(), name="Network"),
        "hardware": Category(id=uuid4(), name="Hardware"),
        "authentication": Category(id=uuid4(), name="Authentication"),
    }


@pytest.fixture
def services():
    return {
        "payment": ITService(id=uuid4(), name="Payment Application", business_criticality=5),
        "portal": ITService(id=uuid4(), name="Employee Portal", business_criticality=3),
        "retired": ITService(id=uuid4(), name="Legacy Intranet", business_criticality=2, is_active=False),
    }


@pytest.fixture
def policies():
    return [
        SLAPolicy(priority=Priority.P1, response_hours=0.0833, resolution_hours=0.5, escalation_hours=0.25),
        SLAPolicy(priority=Priority.P2, response_hours=0.25, resolution_hours=2.0, escalation_hours=1.0),
        SLAPolicy(priority=Priority.P3, response_hours=1.0, resolution_hours=8.0, escalation_hours=4.0),
        SLAPolicy(priority=Priority.P4, response_hours=4.0, resolution_hours=24.0, escalation_hours=8.0),
    ]


@pytest.fixture
def people(categories):
    hashed = hash_password(PASSWORD)
    return {
        "reporter": UserFactory.create(
            Role.EMPLOYEE, employee_code="EMP004", full_name="Ravi Kumar",
            email="ravi@bits.ac.in", password_hash=hashed,
        ),
        "other": UserFactory.create(
            Role.EMPLOYEE, employee_code="EMP006", full_name="Sneha Rao",
            email="sneha@bits.ac.in", password_hash=hashed,
        ),
        "app_tech": UserFactory.create(
            Role.TECHNICIAN, employee_code="EMP002", full_name="Priya Nair",
            email="priya@bits.ac.in", password_hash=hashed,
            skills={categories["application"].id}, experience_level=4, max_workload=5,
        ),
        "net_tech": UserFactory.create(
            Role.TECHNICIAN, employee_code="EMP003", full_name="Arun Das",
            email="arun@bits.ac.in", password_hash=hashed,
            skills={categories["network"].id}, experience_level=2, max_workload=3,
        ),
        "admin": UserFactory.create(
            Role.ADMIN, employee_code="EMP001", full_name="S Iyer",
            email="admin@bits.ac.in", password_hash=hashed,
        ),
    }


@pytest.fixture
def container(services, categories, policies, people):
    return build_test_container(
        services=list(services.values()),
        categories=list(categories.values()),
        policies=policies,
        users=list(people.values()),
    )


@pytest.fixture
def report(container, services, categories, people):
    """Report an incident with sensible defaults, overridable per test."""
    from app.domain.enums import Impact, Urgency

    def _report(**kwargs):
        payload = {
            "reporter": people["reporter"],
            "title": "Payment application is unavailable",
            "description": "Users cannot complete transactions on the payment portal",
            "service_id": services["payment"].id,
            "category_id": categories["application"].id,
            "impact": Impact.HIGH,
            "urgency": Urgency.HIGH,
            "affected_users_count": 40,
        }
        payload.update(kwargs)
        return container.incident_service.report(**payload)

    return _report
