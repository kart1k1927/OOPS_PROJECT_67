"""HTTP level tests.

The application is pointed at the in-memory container, so these exercise the
real routes, the real templates and the real authorisation, with no database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.domain.enums import Status
from tests.conftest import PASSWORD


@pytest.fixture
def client(container):
    deps.set_container(container)
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    deps.set_container(None)


def sign_in(client, email: str) -> None:
    response = client.post("/signin", data={"email": email, "password": PASSWORD}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert "itsm_session" in response.cookies or client.cookies.get("itsm_session")


# --- 43 to 46: access control at the HTTP boundary -----------------------------------


def test_43_pages_require_a_session(client):
    for path in ("/my-incidents", "/queue", "/operations", "/admin/settings"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/signin")


def test_44_each_role_lands_on_its_own_home(client, people):
    for email, expected in [
        ("ravi@bits.ac.in", "/my-incidents"),
        ("priya@bits.ac.in", "/queue"),
        ("admin@bits.ac.in", "/operations"),
    ]:
        response = client.post("/signin", data={"email": email, "password": PASSWORD}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == expected
        client.cookies.clear()


def test_45_an_employee_is_refused_the_admin_pages(client):
    sign_in(client, "ravi@bits.ac.in")
    response = client.get("/operations")
    assert response.status_code == 403
    assert "Administrator accounts" in response.text


def test_46_a_technician_is_refused_the_admin_pages(client):
    sign_in(client, "priya@bits.ac.in")
    assert client.get("/admin/settings").status_code == 403
    assert client.get("/queue").status_code == 200


# --- 47 to 50: the report flow over HTTP -------------------------------------------------


def test_47_reporting_an_incident_through_the_form_works(client, services, categories):
    sign_in(client, "ravi@bits.ac.in")
    response = client.post(
        "/report",
        data={
            "title": "Payment application is unavailable",
            "description": "Users cannot complete transactions",
            "service_id": str(services["payment"].id),
            "category_id": str(categories["application"].id),
            "impact": "HIGH",
            "urgency": "HIGH",
            "affected_users_count": "40",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/incidents/")

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "P1 Critical" in detail.text
    assert "has been logged" in detail.text


def test_48_a_short_title_is_rejected_with_a_readable_message(client, services):
    sign_in(client, "ravi@bits.ac.in")
    response = client.post(
        "/report",
        data={
            "title": "broke", "description": "", "service_id": str(services["payment"].id),
            "category_id": "", "impact": "HIGH", "urgency": "HIGH", "affected_users_count": "1",
        },
    )
    assert response.status_code == 422
    assert "at least 8 characters" in response.text


def test_49_the_live_priority_preview_returns_the_calculation(client, services):
    sign_in(client, "ravi@bits.ac.in")
    response = client.get(
        "/api/incidents/priority-preview",
        params={
            "impact": "HIGH", "urgency": "HIGH",
            "service_id": str(services["payment"].id), "affected_users_count": 40,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "P1"
    assert body["score"] == 47
    assert "criticality 5" in body["explanation"]
    assert "resolve in 30m" in body["sla"]


def test_50_the_category_suggestion_endpoint_works(client):
    sign_in(client, "ravi@bits.ac.in")
    response = client.get(
        "/api/incidents/category-suggestion",
        params={"title": "Cannot login, password reset OTP never arrives", "description": ""},
    )
    assert response.status_code == 200
    assert response.json()["suggestion"]["name"] == "Authentication"


# --- 51 to 53: the work flow over HTTP ------------------------------------------------------


def test_51_a_technician_sees_only_the_permitted_actions(client, report, people):
    incident, _ = report()
    sign_in(client, "priya@bits.ac.in")

    page = client.get(f"/incidents/{incident.id}")
    assert page.status_code == 200
    assert "Acknowledge" in page.text
    assert "Resolve incident" not in page.text, "resolving is not reachable from ASSIGNED"

    client.post(f"/incidents/{incident.id}/action", data={"action": "acknowledge"}, follow_redirects=False)
    client.post(f"/incidents/{incident.id}/action", data={"action": "start_work"}, follow_redirects=False)

    page = client.get(f"/incidents/{incident.id}")
    assert "Resolve incident" in page.text
    assert "Acknowledge" not in page.text


def test_52_a_forged_action_is_refused(client, report, container, people):
    """The UI not offering a button is not the control. The service is."""
    incident, _ = report()
    sign_in(client, "priya@bits.ac.in")

    response = client.post(
        f"/incidents/{incident.id}/action",
        data={"action": "resolve", "note": "Pretending this is fixed."},
    )
    assert response.status_code == 403
    assert container.incidents.get(incident.id).status is Status.ASSIGNED


def test_53_an_admin_can_switch_strategy_from_the_settings_page(client, container):
    sign_in(client, "admin@bits.ac.in")
    assert container.settings.assignment_strategy_name == "skill"

    response = client.post("/admin/settings/assignment", data={"strategy": "round_robin"}, follow_redirects=False)
    assert response.status_code == 303
    assert container.settings.assignment_strategy_name == "round_robin"

    page = client.get("/admin/settings")
    assert "Round robin" in page.text


def test_54_the_search_filters_combine(client, report, people, services, categories):
    from app.domain.enums import Impact, Urgency

    report()
    # Deliberately different on every axis the filter touches.
    report(
        title="Library printer jams on every third page",
        description="The third floor printer needs servicing",
        service_id=services["portal"].id,
        category_id=categories["hardware"].id,
        impact=Impact.LOW,
        urgency=Urgency.LOW,
        affected_users_count=2,
    )
    sign_in(client, "admin@bits.ac.in")

    everything = client.get("/admin/incidents")
    assert everything.status_code == 200

    filtered = client.get("/admin/incidents", params={"priority": "P1", "status": "ASSIGNED", "q": "payment"})
    assert filtered.status_code == 200
    assert "Payment application is unavailable" in filtered.text
    assert "Library printer jams" not in filtered.text

    # And the inverse filter returns the other one.
    inverse = client.get("/admin/incidents", params={"priority": "P4"})
    assert "Library printer jams" in inverse.text
    assert "Payment application is unavailable" not in inverse.text


def test_55_a_missing_incident_renders_a_real_error_page(client):
    sign_in(client, "ravi@bits.ac.in")
    response = client.get("/incidents/11111111-2222-3333-4444-555555555555")
    assert response.status_code == 404
    assert "does not exist" in response.text
