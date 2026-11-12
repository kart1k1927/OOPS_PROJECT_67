"""Spread the demo incidents across the SLA states.

    PYTHONPATH=. .venv/bin/python scripts/age_demo_data.py

Run this before recording the video. Without it the history is either all from
the last five minutes, which makes every SLA read as on track, or aged by a
flat number of hours, which breaches everything at once because a P1 window is
thirty minutes and a P4 window is a day.

The fix is to age each incident as a fraction of its own resolution window:

    on track   10 to 60 percent elapsed
    at risk    78 to 97 percent elapsed
    breached   110 to 320 percent elapsed

Resolved and closed incidents are pushed further back and given a believable
run of lifecycle timestamps, so time to resolve is minutes or hours rather than
the five days since the row happened to be written.
"""

from __future__ import annotations

import pathlib
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.domain.enums import Priority, Status
from app.repositories.mappers import parse_dt
from app.services.container import build_container

# Roughly a third on track, a quarter at risk, a third breached. A helpdesk
# with nothing breached looks staged; one with everything breached looks broken.
OPEN_MIX = (
    [("on_track", 0.10, 0.60)] * 8
    + [("at_risk", 0.78, 0.97)] * 6
    + [("breached", 1.10, 3.20)] * 7
)


def main() -> int:
    rng = random.Random(67)
    container = build_container()
    db = container.incidents._db
    policies = container.catalog.policies_by_priority()
    now = datetime.now(timezone.utc)

    rows = db.table("incidents").select("id,priority,status").limit(500).execute().data
    tally = {"on_track": 0, "at_risk": 0, "breached": 0, "historical": 0}

    for row in rows:
        policy = policies[Priority(row["priority"])]
        window = policy.resolution_target
        status = Status(row["status"])

        if status in (Status.RESOLVED, Status.VERIFIED, Status.CLOSED):
            # Historical. Pushed back over the past two weeks, resolved inside
            # its window so the SLA compliance figures are not all failures.
            created = now - timedelta(days=rng.uniform(1.0, 14.0))
            responded = created + window * rng.uniform(0.05, 0.25)
            resolved = created + window * rng.uniform(0.3, 0.95)
            payload = {
                "created_at": created.isoformat(),
                "first_response_at": responded.isoformat(),
                "acknowledged_at": responded.isoformat(),
                "resolved_at": resolved.isoformat(),
            }
            if status in (Status.VERIFIED, Status.CLOSED):
                payload["verified_at"] = (resolved + timedelta(minutes=rng.uniform(10, 240))).isoformat()
            if status is Status.CLOSED:
                payload["closed_at"] = (resolved + timedelta(minutes=rng.uniform(30, 400))).isoformat()
            tally["historical"] += 1
        else:
            band, low, high = OPEN_MIX[rng.randrange(len(OPEN_MIX))]
            created = now - window * rng.uniform(low, high)
            payload = {"created_at": created.isoformat()}
            tally[band] += 1

        payload.update(
            {
                "response_deadline_at": (created + policy.response_target).isoformat(),
                "resolution_deadline_at": (created + policy.resolution_target).isoformat(),
                "escalation_deadline_at": (created + policy.escalation_target).isoformat(),
            }
        )
        db.table("incidents").update(payload).eq("id", row["id"]).execute()

    print(f"re-aged {len(rows)} incidents: {tally}")
    print("sweep:", container.sla_service.sweep())
    print("overview:", container.reporting.overview())
    return 0


if __name__ == "__main__":
    sys.exit(main())
