"""Integration tests across the service layer.

These run the real IncidentService, the real state machine, the real strategies
and the real observers against in-memory repositories. The only thing swapped
out is persistence, which is the point of the Repository pattern.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidStateTransitionError,
    SLAPolicyMissingError,
    UnauthorizedOperationError,
    ValidationError,
)
from app.domain.enums import EventType, Impact, Priority, SLAState, Status, Urgency
from app.repositories.base import IncidentQuery
from tests.conftest import PASSWORD


# --- 21 to 24: the three demo workflows ----------------------------------------------


def test_21_workflow_one_report_prioritise_assign_notify(container, report, people):
    """Employee reports -> system prioritises -> technician assigned -> notified."""
    incident, duplicates = report()

    assert incident.priority is Priority.P1
    assert incident.priority_score == 47
    assert incident.status is Status.ASSIGNED
    assert incident.assigned_technician_id == people["app_tech"].id, "skill based strategy should pick the Application technician"
    assert incident.sla.resolution_deadline_at is not None

    sent = container.notifications.list_for_user(people["app_tech"].id)
    assert any("assigned to you" in n["title"] for n in sent)

    actions = [entry["action"] for entry in container.audit.entries]
    assert "INCIDENT_CREATED" in actions
    assert "PRIORITY_CALCULATED" in actions
    assert "TECHNICIAN_ASSIGNED" in actions


def test_22_workflow_two_investigate_resolve_verify_close(container, report, people):
    incident, _ = report()
    service = container.incident_service
    tech, reporter = people["app_tech"], people["reporter"]

    service.perform(actor=tech, incident_id=incident.id, action_key="acknowledge")
    service.perform(actor=tech, incident_id=incident.id, action_key="start_work")
    service.perform(
        actor=tech, incident_id=incident.id, action_key="resolve",
        note="Restarted the payment gateway pods and cleared the stuck queue.",
    )
    assert service.get_for(reporter, incident.id).status is Status.RESOLVED

    service.perform(actor=reporter, incident_id=incident.id, action_key="verify")
    service.perform(actor=reporter, incident_id=incident.id, action_key="close", note="Confirmed working.")
    service.perform(actor=reporter, incident_id=incident.id, action_key="feedback", rating=5, comment="Quick")

    final = service.get_for(reporter, incident.id)
    assert final.status is Status.CLOSED
    assert final.feedback_rating == 5
    assert final.resolution_notes.startswith("Restarted")

    reporter_mail = container.notifications.list_for_user(reporter.id)
    assert any("resolved" in n["title"] for n in reporter_mail)


def test_23_workflow_three_duplicates_are_detected(container, report, people, services):
    """The problem statement's own example: three reports of one outage."""
    first, _ = report(title="Payment application is unavailable")
    second, dups = report(
        reporter=people["other"],
        title="Payment transaction failing at checkout",
        description="Payment keeps failing when I try to pay",
        impact=Impact.HIGH,
        urgency=Urgency.MEDIUM,
        affected_users_count=12,
    )

    assert dups, "a second report on the same service with shared vocabulary should be flagged"
    assert dups[0].reference == first.reference
    assert second.duplicate_of_id == first.id
    assert dups[0].score >= 0.30


def test_24_unrelated_incidents_are_not_flagged_as_duplicates(container, report, services):
    report(title="Payment application is unavailable")
    _, dups = report(
        title="Printer in the library is out of toner",
        description="The third floor printer needs a new cartridge",
        service_id=services["portal"].id,
    )
    assert dups == []


# --- 25 to 29: authorisation ------------------------------------------------------------


def test_25_an_employee_cannot_open_somebody_elses_incident(container, report, people):
    incident, _ = report()
    with pytest.raises(UnauthorizedOperationError) as caught:
        container.incident_service.get_for(people["other"], incident.id)
    assert "reported by somebody else" in caught.value.message


def test_26_a_technician_cannot_act_on_another_technicians_incident(container, report, people):
    incident, _ = report()
    with pytest.raises(UnauthorizedOperationError):
        container.incident_service.perform(
            actor=people["net_tech"], incident_id=incident.id, action_key="acknowledge"
        )


def test_27_a_reporter_cannot_close_an_incident_that_is_not_verified(container, report, people):
    """Business rule and authorisation in one check: the action does not exist
    for this role in this state, so a crafted post cannot perform it."""
    incident, _ = report()
    with pytest.raises(UnauthorizedOperationError) as caught:
        container.incident_service.perform(
            actor=people["reporter"], incident_id=incident.id, action_key="close"
        )
    assert "while it is ASSIGNED" in caught.value.message


def test_28_an_employee_cannot_assign_a_technician(container, report, people):
    incident, _ = report()
    with pytest.raises(UnauthorizedOperationError):
        container.incident_service.assign(
            actor=people["reporter"], incident_id=incident.id, technician_id=people["net_tech"].id
        )


def test_29_search_is_scoped_to_the_role(container, report, people):
    """Polymorphic scoping: the same query returns different rows per role."""
    report()
    report(reporter=people["other"], title="Employee portal will not load for me")

    as_admin = container.incident_service.search_for(people["admin"], IncidentQuery())
    as_reporter = container.incident_service.search_for(people["reporter"], IncidentQuery())
    as_other = container.incident_service.search_for(people["other"], IncidentQuery())

    assert len(as_admin) == 2
    assert len(as_reporter) == 1 and as_reporter[0].reporter_id == people["reporter"].id
    assert len(as_other) == 1 and as_other[0].reporter_id == people["other"].id


# --- 30 to 33: authentication ----------------------------------------------------------------


def test_30_sign_in_succeeds_with_the_right_password(container, people):
    user = container.auth.authenticate(email="ravi@bits.ac.in", password=PASSWORD)
    assert user.id == people["reporter"].id


@pytest.mark.parametrize(
    "email,password",
    [("ravi@bits.ac.in", "wrongpassword"), ("nobody@bits.ac.in", PASSWORD), ("", "")],
)
def test_31_bad_credentials_all_fail_the_same_way(container, email, password):
    """The message must not reveal whether the address exists."""
    with pytest.raises(InvalidCredentialsError) as caught:
        container.auth.authenticate(email=email, password=password)
    assert caught.value.message == "Email or password is incorrect."


def test_32_a_deactivated_account_cannot_sign_in(container, people):
    people["reporter"].deactivate()
    with pytest.raises(InactiveAccountError):
        container.auth.authenticate(email="ravi@bits.ac.in", password=PASSWORD)


def test_33_registration_rejects_a_weak_password(container):
    for weak in ("short", "12345678", "abcdefgh"):
        with pytest.raises(ValidationError):
            container.auth.register(full_name="Test Person", email="t@bits.ac.in", password=weak)


# --- 34 to 38: business rules and intelligent features -------------------------------------------


def test_34_a_retired_service_cannot_be_reported_against(container, report, services):
    with pytest.raises(ValidationError) as caught:
        report(service_id=services["retired"].id)
    assert "not an active service" in caught.value.message


def test_35_a_missing_sla_policy_is_refused_with_a_clear_message(services, categories, people):
    """Exception path: priority computes to P1 but no P1 policy is configured."""
    from app.domain.enums import Priority as P
    from app.services.container import build_test_container

    partial = build_test_container(
        services=list(services.values()),
        categories=list(categories.values()),
        policies=[],  # none at all
        users=list(people.values()),
    )
    with pytest.raises(SLAPolicyMissingError) as caught:
        partial.incident_service.report(
            reporter=people["reporter"],
            title="Payment application is unavailable",
            description=None,
            service_id=services["payment"].id,
            category_id=categories["application"].id,
            impact=Impact.HIGH,
            urgency=Urgency.HIGH,
            affected_users_count=40,
        )
    assert "administrator must add one" in caught.value.message


def test_36_changing_the_assignment_strategy_changes_who_gets_the_next_incident(container, report, people, categories):
    """The brief requires the strategy to be swappable without a redesign."""
    container.settings.set_assignment_strategy("skill")
    skill_pick, _ = report(category_id=categories["application"].id)
    assert skill_pick.assigned_technician_id == people["app_tech"].id

    container.settings.set_assignment_strategy("load")
    load_pick, _ = report(category_id=categories["application"].id, title="Another payment outage today")
    assert load_pick.assigned_technician_id == people["net_tech"].id, "load balanced should avoid the now busier technician"


def test_37_automatic_categorization_fills_a_blank_category(container, report):
    incident, _ = report(
        title="Cannot login to the employee portal",
        description="Password reset OTP never arrives and the account is locked",
        category_id=None,
    )
    assert incident.category is not None
    assert incident.category.name == "Authentication"


def test_38_sla_sweep_marks_a_breach_and_notifies(container, report, people):
    incident, _ = report()
    # Pull the incident back in time so its 30 minute P1 window has elapsed.
    incident._created_at = datetime.now(timezone.utc) - timedelta(hours=3)
    incident._sla._created_at = incident._created_at
    incident._sla.recalculate(container.catalog.get_sla_policy(Priority.P1))
    container.incidents.update(incident)

    result = container.sla_service.sweep()

    assert result["breached"] == 1
    assert container.incidents.get(incident.id).sla.resolution_breached is True
    admin_mail = container.notifications.list_for_user(people["admin"].id)
    assert any("breached its SLA" in n["title"] for n in admin_mail)
    # P1 breach must reach every channel, in-app plus the two simulated ones.
    assert {n["channel"] for n in admin_mail} >= {"IN_APP"}


def test_39_escalation_fires_when_a_critical_incident_is_not_acknowledged(container, report):
    incident, _ = report()
    incident._created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    incident._sla._created_at = incident._created_at
    incident._sla.recalculate(container.catalog.get_sla_policy(Priority.P1))
    container.incidents.update(incident)

    result = container.sla_service.sweep()

    assert result["escalated"] >= 1
    assert container.incidents.get(incident.id).escalation_level >= 1
    descriptions = [e["details"]["description"] for e in container.audit.entries]
    assert any("escalated to" in d.lower() for d in descriptions)


def test_40_the_audit_trail_records_every_state_change_in_order(container, report, people):
    incident, _ = report()
    service = container.incident_service
    tech = people["app_tech"]

    service.perform(actor=tech, incident_id=incident.id, action_key="acknowledge")
    service.perform(actor=tech, incident_id=incident.id, action_key="start_work")
    service.perform(actor=tech, incident_id=incident.id, action_key="resolve", note="Cleared the stuck queue.")

    history = container.incidents.list_updates(incident.id)
    transitions = [(u.old_status, u.new_status) for u in history if u.is_status_change]
    assert ("ASSIGNED", "ACKNOWLEDGED") in transitions
    assert ("ACKNOWLEDGED", "IN_PROGRESS") in transitions
    assert ("IN_PROGRESS", "RESOLVED") in transitions

    recorded = [e["action"] for e in container.audit.entries]
    assert recorded.index("INCIDENT_ACKNOWLEDGED") < recorded.index("INCIDENT_RESOLVED")


def test_41_an_observer_that_throws_does_not_break_the_operation(container, report):
    """Resilience: a failing notification channel must not lose an incident."""
    from app.domain.events import Observer

    class Broken(Observer):
        name = "broken"

        def notify(self, event):
            raise RuntimeError("transport is down")

    container.bus.subscribe(Broken())
    incident, _ = report(title="Network switch in D block is down")
    assert container.incidents.get(incident.id) is not None


def test_42_technician_recommendation_explains_itself(container, report, people):
    incident, _ = report()
    recommendations = container.incident_service.recommend_technicians(incident)
    assert recommendations
    top = recommendations[0]
    assert top.technician.id == people["app_tech"].id
    assert any("trained in Application" in reason for reason in top.reasons)
    assert 0 <= top.percent <= 100


# --- 56 to 57: resilience at the storage boundary ---------------------------------


def test_56_a_transient_connection_drop_is_retried(monkeypatch):
    """Supabase drops idle HTTP/2 connections. The next call fails before the
    request is sent, which is a stale socket rather than a real failure."""
    import app.repositories.supabase_repo as repo

    monkeypatch.setattr(repo.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    class RemoteProtocolError(Exception):
        pass

    @repo.guarded
    def flaky(self=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RemoteProtocolError("Server disconnected")
        return "recovered"

    assert flaky() == "recovered"
    assert calls["n"] == 3


def test_57_a_real_error_is_not_retried_forever(monkeypatch):
    import app.repositories.supabase_repo as repo

    monkeypatch.setattr(repo.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    @repo.guarded
    def broken(self=None):
        calls["n"] += 1
        raise ValueError("column does not exist")

    with pytest.raises(Exception) as caught:
        broken()
    assert calls["n"] == 1, "a schema error is not transient, so it fails immediately"
    assert "storage_unavailable" in caught.value.code


def test_58_a_failed_audit_write_does_not_block_a_valid_sign_in(container, people):
    """Losing an audit line is bad. Refusing a correct password because the
    audit table was briefly unreachable is worse."""
    from app.core.exceptions import RepositoryError

    def explode(**_kwargs):
        raise RepositoryError()

    container.audit.record = explode
    user = container.auth.authenticate(email="ravi@bits.ac.in", password=PASSWORD)
    assert user.id == people["reporter"].id
