"""JSON endpoints for incidents.

Only the handful the pages genuinely need. The live priority panel on the
report form is the important one: it calls priority-preview on every change, so
the reporter watches the strategy compute P1 before they submit.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_container, get_current_user
from app.api.presenters import sla_percent, sla_remaining
from app.domain.enums import Impact, Urgency
from app.repositories.base import IncidentQuery

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _summary(incident) -> dict:
    return {
        "id": str(incident.id),
        "reference": incident.reference,
        "title": incident.title,
        "status": incident.status.value,
        "status_label": incident.status.label,
        "priority": incident.priority.value,
        "priority_label": incident.priority.label,
        "service": incident.service.name if incident.service else None,
        "category": incident.category.name if incident.category else None,
        "reporter": incident.reporter_name,
        "technician": incident.technician_name,
        "sla_state": incident.sla_state.value,
        "sla_percent": sla_percent(incident),
        "sla_remaining": sla_remaining(incident),
        "created_at": incident.created_at.isoformat(),
        "updated_at": incident.updated_at.isoformat(),
    }


@router.get("/priority-preview")
def priority_preview(
    impact: Impact = Query(Impact.MEDIUM),
    urgency: Urgency = Query(Urgency.MEDIUM),
    service_id: str = Query(default=""),
    affected_users_count: int = Query(default=1, ge=1, le=100000),
    user=Depends(get_current_user),
):
    """Drives the calculated priority panel on the report form."""
    container = get_container()
    decision = container.incident_service.preview_priority(
        impact=impact,
        urgency=urgency,
        service_id=UUID(service_id) if service_id else None,
        affected_users=affected_users_count,
    )
    policy = container.catalog.get_sla_policy(decision.priority)
    payload = decision.as_dict()
    payload["sla"] = policy.describe() if policy else "no policy configured"
    return payload


@router.get("/category-suggestion")
def category_suggestion(
    title: str = Query(default=""),
    description: str = Query(default=""),
    user=Depends(get_current_user),
):
    container = get_container()
    suggestion = container.incident_service.suggest_category(title, description)
    if suggestion is None:
        return {"suggestion": None}
    category = next((c for c in container.catalog.list_categories() if c.name == suggestion.category_name), None)
    return {
        "suggestion": {
            "id": str(category.id) if category else None,
            "name": suggestion.category_name,
            "confidence": suggestion.confidence,
            "matched": suggestion.matched,
            "explanation": suggestion.explain(),
        }
    }


@router.get("")
def search(
    request_user=Depends(get_current_user),
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    container = get_container()
    query = IncidentQuery(text=q or None, limit=limit, offset=offset)
    incidents = container.incident_service.search_for(request_user, query)
    return {"count": len(incidents), "incidents": [_summary(i) for i in incidents]}


@router.get("/{incident_id}")
def detail(incident_id: UUID, user=Depends(get_current_user)):
    container = get_container()
    incident = container.incident_service.get_for(user, incident_id)
    payload = _summary(incident)
    payload.update(
        {
            "description": incident.description,
            "impact": incident.impact.value,
            "urgency": incident.urgency.value,
            "affected_users_count": incident.affected_users_count,
            "priority_score": incident.priority_score,
            "escalation_level": incident.escalation_level,
            "resolution_notes": incident.resolution_notes,
            "feedback_rating": incident.feedback_rating,
            "allowed_transitions": sorted(s.value for s in incident.allowed_transitions()),
            "available_actions": [a.key for a in user.available_actions(incident)],
            "history": [
                {
                    "at": u.created_at.isoformat(),
                    "author": u.author_name,
                    "type": u.update_type.value,
                    "message": u.message,
                    "from": u.old_status,
                    "to": u.new_status,
                }
                for u in container.incidents.list_updates(incident.id)
            ],
        }
    )
    return payload
