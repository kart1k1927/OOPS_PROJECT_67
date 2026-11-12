"""Populate the database with demo people and incident history.

Run it after applying app/database/migrations/002_app_identity_and_lifecycle.sql:

    PYTHONPATH=. .venv/bin/python scripts/seed_demo.py

Safe to run repeatedly. People are matched on email, so re-running updates them
rather than creating duplicates. Pass --incidents to add another batch of
history; by default it only tops up to the target count.

Without this, every analytics screen and every intelligent feature renders an
empty table, which is no way to record a demo.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import hash_password
from app.database.database import get_client
from app.domain.enums import Impact, Priority, Role, Status, Urgency
from app.repositories.base import IncidentQuery
from app.services.container import build_container

PASSWORD = "campus2026"
TARGET_INCIDENTS = 34

PEOPLE = [
    # (employee_code to reuse if present, full name, email, role, workload, experience, skills)
    ("EMP001", "Sundar Iyer", "admin@bits.ac.in", Role.ADMIN, 5, 5, []),
    ("EMP002", "Priya Nair", "priya@bits.ac.in", Role.TECHNICIAN, 12, 4, ["Application", "Database", "Cloud"]),
    ("EMP003", "Arun Das", "arun@bits.ac.in", Role.TECHNICIAN, 10, 2, ["Network", "Hardware"]),
    (None, "Meera Subramanian", "meera@bits.ac.in", Role.TECHNICIAN, 9, 5, ["Security", "Authentication", "Network"]),
    (None, "Kabir Shah", "kabir@bits.ac.in", Role.TECHNICIAN, 10, 3, ["Software", "Storage", "Hardware"]),
    ("EMP004", "Ravi Kumar", "ravi@bits.ac.in", Role.EMPLOYEE, 5, 1, []),
    (None, "Sneha Rao", "sneha@bits.ac.in", Role.EMPLOYEE, 5, 1, []),
    (None, "Imran Qureshi", "imran@bits.ac.in", Role.EMPLOYEE, 5, 1, []),
    (None, "Divya Menon", "divya@bits.ac.in", Role.EMPLOYEE, 5, 1, []),
]

# (title, description, category, service, impact, urgency, affected)
SCENARIOS = [
    ("Payment application is unavailable", "Users cannot complete transactions on the payment portal and get a 500 error.",
     "Application", "Payment Application", Impact.HIGH, Urgency.HIGH, 120),
    ("Payment transaction failing at checkout", "Payment keeps failing when I try to pay the hostel fee.",
     "Application", "Payment Application", Impact.HIGH, Urgency.MEDIUM, 18),
    ("Unable to make payment on the portal", "The payment page errors out after I enter the card details.",
     "Application", "Payment Application", Impact.MEDIUM, Urgency.MEDIUM, 6),
    ("Campus wifi keeps disconnecting in D block", "The wifi drops every few minutes on the second floor.",
     "Network", "Network Infrastructure", Impact.HIGH, Urgency.HIGH, 85),
    ("VPN will not connect from outside campus", "The VPN client times out when connecting from home.",
     "Network", "Network Infrastructure", Impact.MEDIUM, Urgency.HIGH, 24),
    ("Cannot login to the employee portal", "Password reset OTP never arrives and the account is now locked.",
     "Authentication", "Employee Portal", Impact.MEDIUM, Urgency.HIGH, 3),
    ("Single sign on returns an invalid token error", "SSO fails with an invalid token message after the redirect.",
     "Authentication", "Employee Portal", Impact.HIGH, Urgency.HIGH, 40),
    ("Email delivery is delayed by several hours", "Mail sent this morning has still not arrived.",
     "Software", "Email Service", Impact.MEDIUM, Urgency.MEDIUM, 60),
    ("Mailbox quota exceeded and mail is bouncing", "I cannot receive mail, the quota is full.",
     "Storage", "Email Service", Impact.MEDIUM, Urgency.MEDIUM, 1),
    ("Postgres query deadlock on the results table", "Deadlock detected during peak result publishing.",
     "Database", "Employee Portal", Impact.HIGH, Urgency.HIGH, 30),
    ("Database backup job failed overnight", "The nightly backup reported a write error.",
     "Database", "Employee Portal", Impact.HIGH, Urgency.LOW, 2),
    ("Laptop battery is not charging", "The charger light stays amber and the battery does not fill.",
     "Hardware", None, Impact.LOW, Urgency.MEDIUM, 1),
    ("Projector in LT3 will not display", "No signal shown when the laptop is connected.",
     "Hardware", None, Impact.MEDIUM, Urgency.HIGH, 45),
    ("Printer on the library third floor jams constantly", "Paper jams on roughly every third page.",
     "Hardware", None, Impact.LOW, Urgency.LOW, 12),
    ("Suspicious phishing email asking for credentials", "Received a mail pretending to be from IT asking for my password.",
     "Security", "Email Service", Impact.HIGH, Urgency.HIGH, 200),
    ("Antivirus flagged malware on a lab machine", "The lab PC reports a quarantined trojan.",
     "Security", None, Impact.MEDIUM, Urgency.HIGH, 4),
    ("Cloud storage bucket is not accessible", "Requests to the research data bucket return access denied.",
     "Cloud", "Payment Application", Impact.MEDIUM, Urgency.MEDIUM, 8),
    ("Kubernetes pod restarts repeatedly", "The deployment keeps crash looping after the last release.",
     "Cloud", "Payment Application", Impact.HIGH, Urgency.MEDIUM, 35),
    ("MATLAB licence server is unreachable", "MATLAB will not start, it cannot reach the licence server.",
     "Software", None, Impact.MEDIUM, Urgency.MEDIUM, 22),
    ("Excel crashes when opening the marks sheet", "Excel closes immediately when I open the consolidated marks file.",
     "Software", None, Impact.LOW, Urgency.MEDIUM, 2),
    ("Shared drive has run out of space", "The department share reports zero bytes free.",
     "Storage", None, Impact.MEDIUM, Urgency.HIGH, 50),
    ("Portal dashboard loads very slowly", "The dashboard takes over thirty seconds to render.",
     "Application", "Employee Portal", Impact.LOW, Urgency.MEDIUM, 70),
]

RESOLUTIONS = {
    "Application": "Restarted the application pods and cleared the stuck request queue. Verified with a test transaction.",
    "Network": "Replaced the faulty access point and moved the block onto the redundant uplink.",
    "Authentication": "Cleared the stale session entries and reissued the signing key. Asked the user to sign in again.",
    "Database": "Killed the blocking session, added the missing index and reran the job.",
    "Hardware": "Swapped the faulty unit from spares and raised a replacement request with the vendor.",
    "Security": "Blocked the sender domain, reset the affected credentials and circulated a warning notice.",
    "Cloud": "Corrected the bucket policy and redeployed with the right service account.",
    "Software": "Reinstalled the client and pointed it at the current licence server.",
    "Storage": "Extended the volume and archived files older than two years.",
}


def ensure_people(container, db) -> dict:
    categories = {c.name: c for c in container.catalog.list_categories()}
    hashed = hash_password(PASSWORD)
    people: dict[str, object] = {}

    for code, name, email, role, workload, experience, skills in PEOPLE:
        existing = db.table("profiles").select("*").ilike("email", email).limit(1).execute().data
        if not existing and code:
            existing = db.table("profiles").select("*").eq("employee_code", code).limit(1).execute().data

        payload = {
            "full_name": name,
            "email": email,
            "role": role.value,
            "password_hash": hashed,
            "is_active": True,
            "max_workload": workload,
            "experience_level": experience,
        }

        if existing:
            row_id = existing[0]["id"]
            db.table("profiles").update(payload).eq("id", row_id).execute()
            action = "updated"
        else:
            payload["id"] = str(uuid4())
            row_id = db.table("profiles").insert(payload).execute().data[0]["id"]
            action = "created"

        if role is Role.TECHNICIAN:
            db.table("technician_skills").delete().eq("technician_id", row_id).execute()
            rows = [
                {"technician_id": row_id, "category_id": str(categories[s].id)}
                for s in skills if s in categories
            ]
            if rows:
                db.table("technician_skills").insert(rows).execute()

        people[email] = row_id
        print(f"  {action:8s} {name:22s} {role.value:11s} {email}")

    return people


def seed_incidents(container, people, count: int) -> None:
    rng = random.Random(67)  # group number, so the demo data is reproducible
    service_lookup = {s.name: s for s in container.catalog.list_services()}
    category_lookup = {c.name: c for c in container.catalog.list_categories()}
    employees = [
        container.users.get_by_email(e)
        for e in ("ravi@bits.ac.in", "sneha@bits.ac.in", "imran@bits.ac.in", "divya@bits.ac.in")
    ]
    employees = [e for e in employees if e is not None]
    if not employees:
        print("  no employees found, cannot seed incidents")
        return

    service = container.incident_service
    made = 0
    attempt = 0

    while made < count:
        scenario = SCENARIOS[attempt % len(SCENARIOS)]
        attempt += 1
        title, description, category_name, service_name, impact, urgency, affected = scenario
        suffix = "" if attempt <= len(SCENARIOS) else f" ({attempt // len(SCENARIOS) + 1})"

        reporter = employees[attempt % len(employees)]
        try:
            incident, _ = service.report(
                reporter=reporter,
                title=title + suffix,
                description=description,
                service_id=service_lookup[service_name].id if service_name in service_lookup else None,
                category_id=category_lookup[category_name].id if category_name in category_lookup else None,
                impact=impact,
                urgency=urgency,
                affected_users_count=affected,
            )
        except Exception as exc:
            print(f"  skipped {title[:40]}: {str(exc)[:80]}")
            continue

        made += 1

        # Age the incident so the history is not all from the last minute.
        # The three deadlines derive from created_at, so they have to move with
        # it. Writing created_at alone stretches the SLA window to match the new
        # age, which makes every aged incident read as 99 percent elapsed and
        # never breach.
        age_hours = rng.choice([1, 3, 6, 12, 24, 36, 48, 72, 96, 120])
        created = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        policy = container.catalog.get_sla_policy(incident.priority)
        container.incidents._db.table("incidents").update(
            {
                "created_at": created.isoformat(),
                "response_deadline_at": (created + policy.response_target).isoformat(),
                "resolution_deadline_at": (created + policy.resolution_target).isoformat(),
                "escalation_deadline_at": (created + policy.escalation_target).isoformat(),
            }
        ).eq("id", str(incident.id)).execute()

        # Walk a realistic proportion through the lifecycle.
        roll = rng.random()
        if roll < 0.18:
            continue  # leave it sitting at ASSIGNED, so some SLAs breach

        technician = container.users.get(incident.assigned_technician_id) if incident.assigned_technician_id else None
        if technician is None:
            continue

        try:
            service.perform(actor=technician, incident_id=incident.id, action_key="acknowledge")
            if roll < 0.32:
                continue
            service.perform(actor=technician, incident_id=incident.id, action_key="start_work")
            if roll < 0.45:
                continue
            service.perform(
                actor=technician,
                incident_id=incident.id,
                action_key="resolve",
                note=RESOLUTIONS.get(category_name, "Investigated and corrected the underlying fault."),
            )
            if roll < 0.62:
                continue
            service.perform(actor=reporter, incident_id=incident.id, action_key="verify")
            service.perform(actor=reporter, incident_id=incident.id, action_key="close", note="Confirmed by the reporter.")
            if roll < 0.85:
                continue
            service.perform(
                actor=reporter, incident_id=incident.id, action_key="feedback",
                rating=rng.choice([5, 5, 4, 4, 3]), comment=rng.choice(["Quick work.", "Sorted the same day.", ""]),
            )
        except Exception as exc:
            print(f"  {incident.reference} stopped early: {str(exc)[:70]}")

    print(f"  seeded {made} incidents")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo data for I-ITSM.")
    parser.add_argument("--incidents", type=int, default=0, help="Add this many incidents regardless of the current count.")
    parser.add_argument("--reset-passwords", action="store_true", help="Only reset every demo password.")
    args = parser.parse_args()

    db = get_client()

    try:
        db.table("profiles").select("full_name").limit(1).execute()
    except Exception:
        print("Migration 002 has not been applied yet.")
        print("Open the Supabase dashboard, go to SQL Editor, paste the contents of")
        print("  app/database/migrations/002_app_identity_and_lifecycle.sql")
        print("and run it. Then run this script again.")
        return 1

    container = build_container()

    print("People:")
    people = ensure_people(container, db)

    if args.reset_passwords:
        print(f"\nAll demo passwords are now: {PASSWORD}")
        return 0

    current = container.incidents.count(IncidentQuery())
    wanted = args.incidents if args.incidents else max(0, TARGET_INCIDENTS - current)
    print(f"\nIncidents: {current} present, adding {wanted}")
    if wanted:
        seed_incidents(container, people, wanted)

    print("\nSpreading the incidents across the SLA states.")
    from scripts.age_demo_data import main as age_demo_data
    age_demo_data()

    print("\nSign in with any of these, password " + PASSWORD + ":")
    print("  admin@bits.ac.in   Administrator")
    print("  priya@bits.ac.in   Technician")
    print("  ravi@bits.ac.in    Employee")
    return 0


if __name__ == "__main__":
    sys.exit(main())
