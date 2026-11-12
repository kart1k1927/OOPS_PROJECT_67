"""Run the whole application against in-memory repositories.

    PYTHONPATH=. .venv/bin/python scripts/demo_server.py

Useful when somebody on the team does not have the Supabase keys, or when you
want to show the interface without touching real data. Everything works except
persistence: restart it and the data is gone.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import random
from uuid import uuid4

import uvicorn

from app.api import deps
from app.core.security import hash_password
from app.domain.catalog import Category, ITService, SLAPolicy
from app.domain.enums import Impact, Priority, Role, Urgency
from app.domain.factories import UserFactory
from app.services.container import build_test_container

PASSWORD = "campus2026"

CATEGORY_NAMES = [
    "Hardware", "Software", "Network", "Database", "Cloud",
    "Security", "Authentication", "Application", "Storage",
]

SERVICES = [
    ("Payment Application", 5), ("Network Infrastructure", 5),
    ("Email Service", 4), ("Employee Portal", 3),
]

POLICIES = [
    (Priority.P1, 0.0833, 0.5, 0.25),
    (Priority.P2, 0.25, 2.0, 1.0),
    (Priority.P3, 1.0, 8.0, 4.0),
    (Priority.P4, 4.0, 24.0, 8.0),
]

TECHNICIANS = [
    ("Priya Nair", "priya@bits.ac.in", 6, 4, ["Application", "Database", "Cloud"]),
    ("Arun Das", "arun@bits.ac.in", 5, 2, ["Network", "Hardware"]),
    ("Meera Subramanian", "meera@bits.ac.in", 4, 5, ["Security", "Authentication", "Network"]),
    ("Kabir Shah", "kabir@bits.ac.in", 5, 3, ["Software", "Storage"]),
]

EMPLOYEES = [
    ("Ravi Kumar", "ravi@bits.ac.in"), ("Sneha Rao", "sneha@bits.ac.in"),
    ("Imran Qureshi", "imran@bits.ac.in"), ("Divya Menon", "divya@bits.ac.in"),
]


def build() -> object:
    from scripts.seed_demo import RESOLUTIONS, SCENARIOS

    categories = {name: Category(id=uuid4(), name=name) for name in CATEGORY_NAMES}
    services = {name: ITService(id=uuid4(), name=name, business_criticality=c) for name, c in SERVICES}
    policies = [
        SLAPolicy(priority=p, response_hours=r, resolution_hours=res, escalation_hours=e)
        for p, r, res, e in POLICIES
    ]
    hashed = hash_password(PASSWORD)

    people = [UserFactory.create(Role.ADMIN, employee_code="EMP001", full_name="Sundar Iyer",
                                 email="admin@bits.ac.in", password_hash=hashed)]
    for index, (name, email, capacity, experience, skills) in enumerate(TECHNICIANS, start=2):
        people.append(UserFactory.create(
            Role.TECHNICIAN, employee_code=f"EMP{index:03d}", full_name=name, email=email,
            password_hash=hashed, max_workload=capacity, experience_level=experience,
            skills={categories[s].id for s in skills}, skill_names=tuple(skills),
        ))
    for index, (name, email) in enumerate(EMPLOYEES, start=len(TECHNICIANS) + 2):
        people.append(UserFactory.create(
            Role.EMPLOYEE, employee_code=f"EMP{index:03d}", full_name=name, email=email, password_hash=hashed,
        ))

    container = build_test_container(
        services=list(services.values()),
        categories=list(categories.values()),
        policies=policies,
        users=people,
    )

    employees = [p for p in people if p.role is Role.EMPLOYEE]
    rng = random.Random(67)
    service_instance = container.incident_service

    for index, scenario in enumerate(SCENARIOS):
        title, description, category_name, service_name, impact, urgency, affected = scenario
        reporter = employees[index % len(employees)]
        try:
            incident, _ = service_instance.report(
                reporter=reporter, title=title, description=description,
                service_id=services[service_name].id if service_name in services else None,
                category_id=categories[category_name].id if category_name in categories else None,
                impact=impact, urgency=urgency, affected_users_count=affected,
            )
        except Exception:
            continue

        roll = rng.random()
        technician = container.users.get(incident.assigned_technician_id) if incident.assigned_technician_id else None
        if technician is None or roll < 0.2:
            continue
        try:
            service_instance.perform(actor=technician, incident_id=incident.id, action_key="acknowledge")
            if roll < 0.34:
                continue
            service_instance.perform(actor=technician, incident_id=incident.id, action_key="start_work")
            if roll < 0.47:
                continue
            service_instance.perform(
                actor=technician, incident_id=incident.id, action_key="resolve",
                note=RESOLUTIONS.get(category_name, "Investigated and corrected the fault."),
            )
            if roll < 0.66:
                continue
            service_instance.perform(actor=reporter, incident_id=incident.id, action_key="verify")
            service_instance.perform(actor=reporter, incident_id=incident.id, action_key="close",
                                     note="Confirmed by the reporter.")
            if roll < 0.86:
                continue
            service_instance.perform(actor=reporter, incident_id=incident.id, action_key="feedback",
                                     rating=rng.choice([5, 5, 4, 3]), comment="Sorted quickly.")
        except Exception:
            pass

    container.sla_service.sweep()
    return container


if __name__ == "__main__":
    deps.set_container(build())
    print("\n  Demo server, in-memory data. Password for everyone: " + PASSWORD)
    print("  admin@bits.ac.in  ·  priya@bits.ac.in  ·  ravi@bits.ac.in\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
