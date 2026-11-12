"""Unit tests for the domain layer. No repositories, no services, no I/O."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import (
    InvalidStateTransitionError,
    TechnicianUnavailableError,
    ValidationError,
)
from app.domain.assignment import (
    ExperienceBasedAssignment,
    LoadBalancedAssignment,
    RoundRobinAssignment,
    SkillBasedAssignment,
)
from app.domain.catalog import ITService, SLAPolicy
from app.domain.enums import Impact, Priority, SLAState, Status, Urgency
from app.domain.incident import Incident
from app.domain.priority import MatrixPriorityStrategy, WeightedPriorityStrategy
from app.domain.sla import SLATracker
from app.domain.states import state_for, transition_graph


def make_incident(**kwargs) -> Incident:
    defaults = {"reporter_id": uuid4(), "title": "Payment application is unavailable"}
    defaults.update(kwargs)
    return Incident(**defaults)


# --- 1. business rule: the lifecycle is enforced ---------------------------------


def test_01_new_incident_cannot_jump_straight_to_closed():
    """The problem statement names OPEN -> CLOSED as the transition that must
    not be allowed without intermediate processing."""
    incident = make_incident()
    with pytest.raises(InvalidStateTransitionError) as caught:
        incident.transition_to(Status.CLOSED)
    assert incident.status is Status.OPEN
    assert "cannot move to CLOSED" in caught.value.message
    assert "ASSIGNED" in caught.value.message


def test_02_full_lifecycle_runs_in_order():
    incident = make_incident()
    technician, reporter = uuid4(), incident.reporter_id
    incident.assign_to(technician, technician_name="Priya Nair")
    assert incident.status is Status.ASSIGNED

    incident.acknowledge(actor_id=technician)
    incident.start_work(actor_id=technician)
    incident.resolve("Restarted the payment gateway pods.", actor_id=technician)
    incident.verify(actor_id=reporter)
    incident.close("Confirmed.", actor_id=reporter)

    assert incident.status is Status.CLOSED
    assert incident.acknowledged_at and incident.resolved_at and incident.verified_at and incident.closed_at
    assert incident.first_response_at == incident.acknowledged_at


def test_03_closed_is_terminal():
    """Boundary condition: the last state has no exits at all."""
    assert state_for(Status.CLOSED).allowed_transitions() == frozenset()
    graph = transition_graph()
    assert graph["CLOSED"] == []
    assert "CLOSED" not in graph["OPEN"]


def test_04_resolved_can_be_reopened_but_not_reassigned_backwards():
    incident = make_incident()
    technician = uuid4()
    incident.assign_to(technician)
    incident.acknowledge(actor_id=technician)
    incident.start_work(actor_id=technician)
    incident.resolve("Looks fixed from here.", actor_id=technician)

    incident.reopen("Still failing for me.", actor_id=incident.reporter_id)
    assert incident.status is Status.IN_PROGRESS

    with pytest.raises(InvalidStateTransitionError):
        incident.transition_to(Status.VERIFIED)


# --- 2. invalid input ------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,reason",
    [("", "empty"), ("short", "too short"), ("x" * 200, "too long")],
)
def test_05_titles_are_validated(title, reason):
    with pytest.raises(ValidationError):
        make_incident(title=title)


@pytest.mark.parametrize("count", [0, -5, "many"])
def test_06_affected_user_count_is_validated(count):
    with pytest.raises(ValidationError):
        make_incident(affected_users_count=count)


def test_07_resolution_requires_a_real_explanation():
    """Boundary: exactly at the 10 character minimum passes, under it fails."""
    incident = make_incident()
    technician = uuid4()
    incident.assign_to(technician)
    incident.acknowledge(actor_id=technician)
    incident.start_work(actor_id=technician)

    with pytest.raises(ValidationError) as caught:
        incident.resolve("fixed", actor_id=technician)
    assert "10 characters" in caught.value.message
    assert incident.status is Status.IN_PROGRESS

    incident.resolve("rebooted it", actor_id=technician)
    assert incident.status is Status.RESOLVED


def test_08_feedback_is_bounded_and_only_after_resolution():
    incident = make_incident()
    with pytest.raises(ValidationError):
        incident.record_feedback(5)

    technician = uuid4()
    incident.assign_to(technician)
    incident.acknowledge(actor_id=technician)
    incident.start_work(actor_id=technician)
    incident.resolve("Cleared the stuck queue.", actor_id=technician)

    for bad in (0, 6, "five"):
        with pytest.raises(ValidationError):
            incident.record_feedback(bad)
    incident.record_feedback(4, "Quick work")
    assert incident.feedback_rating == 4


# --- 3. priority strategies ---------------------------------------------------------------


def test_09_weighted_priority_matches_the_documented_formula():
    decision = WeightedPriorityStrategy().calculate(
        impact=Impact.HIGH, urgency=Urgency.HIGH, business_criticality=5, affected_users=40
    )
    assert decision.priority is Priority.P1
    assert decision.score == 47  # 3 x 3 x 5 = 45, plus 2 for more than 10 people
    assert "criticality 5" in decision.explanation


@pytest.mark.parametrize(
    "impact,urgency,criticality,expected",
    [
        (Impact.HIGH, Urgency.HIGH, 5, Priority.P1),
        (Impact.HIGH, Urgency.HIGH, 3, Priority.P2),
        (Impact.MEDIUM, Urgency.MEDIUM, 3, Priority.P3),
        (Impact.LOW, Urgency.LOW, 3, Priority.P4),
        (Impact.LOW, Urgency.LOW, 1, Priority.P4),
    ],
)
def test_10_priority_bands_cover_the_whole_range(impact, urgency, criticality, expected):
    decision = WeightedPriorityStrategy().calculate(
        impact=impact, urgency=urgency, business_criticality=criticality, affected_users=1
    )
    assert decision.priority is expected


def test_11_the_two_priority_strategies_are_interchangeable_and_differ():
    """Polymorphism: same call, same return type, different policy."""
    args = {"impact": Impact.HIGH, "urgency": Urgency.LOW, "business_criticality": 5, "affected_users": 1}
    weighted = WeightedPriorityStrategy().calculate(**args)
    matrix = MatrixPriorityStrategy().calculate(**args)

    # Same call signature, same return type, different answer. That is the
    # substitutability the Strategy pattern is for.
    assert type(weighted) is type(matrix)
    assert weighted.priority is Priority.P3, "score 15 is under the 18 point P2 threshold"
    assert matrix.priority is Priority.P2, "HIGH/LOW gives P3, upgraded one level by criticality 5"
    assert weighted.priority is not matrix.priority, "the two policies genuinely disagree here"
    assert weighted.score == matrix.score == 15
    assert weighted.explanation != matrix.explanation


# --- 4. assignment strategies ----------------------------------------------------------------


class FakeTechnician:
    """Only what AssignmentStrategy actually touches."""

    def __init__(self, code, *, skills=(), load=0, capacity=5, experience=1, active=True):
        self.employee_code = code
        self.full_name = code
        self.id = uuid4()
        self._skills = set(skills)
        self.active_workload = load
        self.max_workload = capacity
        self.experience_level = experience
        self.is_active = active

    def knows(self, category_id):
        return category_id in self._skills

    @property
    def has_capacity(self):
        return self.active_workload < self.max_workload

    @property
    def load_fraction(self):
        return self.active_workload / self.max_workload

    @property
    def spare_capacity(self):
        return self.max_workload - self.active_workload

    def is_available_for(self, incident):
        return self.is_active and self.has_capacity


def test_12_each_strategy_picks_a_different_technician_for_the_same_incident(categories):
    network = categories["network"]
    incident = make_incident(category=network, service=ITService(id=uuid4(), name="X", business_criticality=5))
    incident.apply_priority(Priority.P1)

    skilled_busy = FakeTechnician("EMP002", skills={network.id}, load=3, experience=4)
    idle_unskilled = FakeTechnician("EMP003", load=1, experience=2)
    senior_skilled = FakeTechnician("EMP005", skills={network.id}, load=4, experience=5)
    pool = [skilled_busy, idle_unskilled, senior_skilled]

    assert SkillBasedAssignment().select(incident, pool).technician is skilled_busy
    assert LoadBalancedAssignment().select(incident, pool).technician is idle_unskilled
    assert ExperienceBasedAssignment().select(incident, pool).technician is senior_skilled


def test_13_no_strategy_assigns_past_a_workload_ceiling():
    """Business rule: a technician at capacity is never selected."""
    incident = make_incident()
    full = [FakeTechnician("EMP002", load=5, capacity=5), FakeTechnician("EMP003", load=3, capacity=3)]
    for strategy in (SkillBasedAssignment(), LoadBalancedAssignment(), RoundRobinAssignment(), ExperienceBasedAssignment()):
        with pytest.raises(TechnicianUnavailableError) as caught:
            strategy.select(incident, full)
        assert "workload limit" in caught.value.message


def test_14_inactive_technicians_are_never_selected():
    incident = make_incident()
    pool = [FakeTechnician("EMP002", load=0, active=False), FakeTechnician("EMP003", load=2)]
    chosen = LoadBalancedAssignment().select(incident, pool).technician
    assert chosen.employee_code == "EMP003"


def test_15_round_robin_actually_rotates():
    incident = make_incident()
    pool = [FakeTechnician("EMP002"), FakeTechnician("EMP003"), FakeTechnician("EMP004")]
    strategy = RoundRobinAssignment()
    picked = [strategy.select(incident, pool).technician.employee_code for _ in range(6)]
    assert picked == ["EMP002", "EMP003", "EMP004", "EMP002", "EMP003", "EMP004"]


def test_16_assignment_with_no_technicians_at_all_is_reported_clearly():
    with pytest.raises(TechnicianUnavailableError) as caught:
        SkillBasedAssignment().select(make_incident(), [])
    assert "No technicians are registered" in caught.value.message


# --- 5. SLA arithmetic --------------------------------------------------------------------------


def test_17_sla_deadlines_derive_from_the_policy():
    created = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
    policy = SLAPolicy(priority=Priority.P1, response_hours=0.0833, resolution_hours=0.5, escalation_hours=0.25)
    tracker = SLATracker(created_at=created, policy=policy)

    # 0.0833 hours is five minutes to within a tenth of a second, which is the
    # precision the sla_policies column now carries.
    assert abs((tracker.response_deadline_at - (created + timedelta(minutes=5))).total_seconds()) < 1
    assert tracker.resolution_deadline_at == created + timedelta(minutes=30)
    assert tracker.escalation_deadline_at == created + timedelta(minutes=15)


@pytest.mark.parametrize(
    "minutes_elapsed,expected",
    [(0, SLAState.ON_TRACK), (14, SLAState.ON_TRACK), (23, SLAState.AT_RISK), (31, SLAState.BREACHED)],
)
def test_18_sla_state_crosses_at_the_documented_thresholds(minutes_elapsed, expected):
    """Boundary: at risk begins at 75 percent of the window, breached past 100."""
    now = datetime.now(timezone.utc)
    created = now - timedelta(minutes=minutes_elapsed)
    policy = SLAPolicy(priority=Priority.P1, response_hours=0.0833, resolution_hours=0.5, escalation_hours=0.25)
    tracker = SLATracker(created_at=created, policy=policy)
    assert tracker.state(now=now) is expected


def test_19_resolving_inside_the_window_counts_as_met_not_breached():
    now = datetime.now(timezone.utc)
    created = now - timedelta(hours=10)
    policy = SLAPolicy(priority=Priority.P3, response_hours=1, resolution_hours=8, escalation_hours=4)
    tracker = SLATracker(created_at=created, policy=policy)

    assert tracker.state(now=now) is SLAState.BREACHED
    assert tracker.state(resolved_at=created + timedelta(hours=2), now=now) is SLAState.MET


def test_20_priority_change_moves_the_deadline_with_it():
    """Business rule: priority and SLA cannot drift apart."""
    incident = make_incident()
    p3 = SLAPolicy(priority=Priority.P3, response_hours=1, resolution_hours=8, escalation_hours=4)
    p1 = SLAPolicy(priority=Priority.P1, response_hours=0.0833, resolution_hours=0.5, escalation_hours=0.25)

    incident.apply_priority(Priority.P3, policy=p3)
    relaxed = incident.sla.resolution_deadline_at

    incident.apply_priority(Priority.P1, policy=p1)
    assert incident.sla.resolution_deadline_at < relaxed
    assert incident.priority is Priority.P1
