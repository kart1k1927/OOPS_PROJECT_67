"""Technician facing endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_container, get_current_user, require_admin

router = APIRouter(prefix="/api/technicians", tags=["technicians"])


@router.get("")
def list_technicians(user=Depends(get_current_user)):
    container = get_container()
    return {
        "technicians": [
            {
                "id": str(t.id),
                "employee_code": t.employee_code,
                "name": t.full_name,
                "active": t.active_workload,
                "capacity": t.max_workload,
                "experience": t.experience_level,
                "skills": list(t.skill_names),
                "has_capacity": t.has_capacity,
                "is_active": t.is_active,
            }
            for t in container.users.list_technicians()
        ]
    }


@router.get("/recommend/{incident_id}")
def recommend(incident_id: UUID, user=Depends(require_admin)):
    """Smart technician recommendation, with the reasoning shown."""
    container = get_container()
    incident = container.incident_service.get_for(user, incident_id)
    return {
        "incident": incident.reference,
        "recommendations": [
            {
                "id": str(r.technician.id),
                "employee_code": r.technician.employee_code,
                "name": r.technician.full_name,
                "score": r.percent,
                "reasons": r.reasons,
            }
            for r in container.incident_service.recommend_technicians(incident)
        ],
    }


@router.get("/me/workload")
def my_workload(user=Depends(get_current_user)):
    if not hasattr(user, "active_workload"):
        return {"active": 0, "capacity": 0}
    return {
        "active": user.active_workload,
        "capacity": user.max_workload,
        "spare": user.spare_capacity,
        "resolved": user.resolved_count,
        "skills": list(user.skill_names),
    }
