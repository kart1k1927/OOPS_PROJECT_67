"""Administrator write endpoints.

All form posts followed by a redirect. The settings handlers are the ones worth
reading: they swap the strategy object the whole system uses, at runtime, with
no restart and no code change anywhere else.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse

from app.api.deps import get_container, require_admin
from app.core.exceptions import ValidationError
from app.domain.catalog import Category, ITService, SLAPolicy
from app.domain.enums import Priority, Role

router = APIRouter(prefix="/admin", tags=["admin"])


def _back(path: str = "/admin/settings") -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


@router.post("/settings/assignment")
def set_assignment_strategy(strategy: str = Form(...), user=Depends(require_admin)):
    container = get_container()
    try:
        container.settings.set_assignment_strategy(strategy)
    except KeyError:
        raise ValidationError(f"{strategy} is not a registered assignment strategy.", field="strategy") from None
    container.audit.record(
        actor_id=user.id,
        action="SETTING_CHANGED",
        entity_type="settings",
        entity_id=None,
        details={
            "description": f"Assignment strategy set to {container.settings.assignment_strategy.label} by {user.full_name}.",
            "actor_name": user.full_name,
        },
    )
    return _back()


@router.post("/settings/priority")
def set_priority_strategy(strategy: str = Form(...), user=Depends(require_admin)):
    container = get_container()
    try:
        container.settings.set_priority_strategy(strategy)
    except KeyError:
        raise ValidationError(f"{strategy} is not a registered priority strategy.", field="strategy") from None
    container.audit.record(
        actor_id=user.id,
        action="SETTING_CHANGED",
        entity_type="settings",
        entity_id=None,
        details={
            "description": f"Priority strategy set to {strategy} by {user.full_name}.",
            "actor_name": user.full_name,
        },
    )
    return _back()


@router.post("/settings/toggle")
def toggle_feature(key: str = Form(...), value: str = Form(default="0"), user=Depends(require_admin)):
    container = get_container()
    try:
        container.settings.toggle(key, value == "1")
    except KeyError:
        raise ValidationError(f"{key} is not a setting.", field="key") from None
    return _back()


@router.post("/sla/sweep")
def run_sla_sweep(user=Depends(require_admin)):
    """Runs the monitor immediately instead of waiting for the next tick.
    Used in the demo so SLA breaches can be shown on cue."""
    get_container().sla_service.sweep()
    return _back("/operations")


@router.post("/people/{user_id}/role")
def change_role(user_id: UUID, role: str = Form(...), user=Depends(require_admin)):
    container = get_container()
    container.users.set_role(user_id, Role(role))
    container.audit.record(
        actor_id=user.id,
        action="ROLE_CHANGED",
        entity_type="user",
        entity_id=user_id,
        details={"description": f"Role changed to {role} by {user.full_name}.", "actor_name": user.full_name},
    )
    return _back("/admin/people")


@router.post("/people/{user_id}/active")
def set_active(user_id: UUID, active: str = Form(default="1"), user=Depends(require_admin)):
    container = get_container()
    container.users.set_active(user_id, active == "1")
    container.audit.record(
        actor_id=user.id,
        action="USER_DEACTIVATED" if active != "1" else "USER_ACTIVATED",
        entity_type="user",
        entity_id=user_id,
        details={"description": f"Account set {'active' if active == '1' else 'inactive'} by {user.full_name}.", "actor_name": user.full_name},
    )
    return _back("/admin/people")


@router.post("/people/{user_id}/skills")
def set_skills(user_id: UUID, category_ids: list[str] = Form(default=[]), user=Depends(require_admin)):
    container = get_container()
    container.users.set_skills(user_id, [UUID(c) for c in category_ids if c])
    return _back("/admin/people")


@router.post("/catalog/service")
def add_service(
    name: str = Form(...),
    description: str = Form(default=""),
    business_criticality: int = Form(default=3),
    user=Depends(require_admin),
):
    container = get_container()
    from uuid import uuid4

    container.catalog.add_service(
        ITService(id=uuid4(), name=name.strip(), description=description.strip() or None, business_criticality=business_criticality)
    )
    return _back("/admin/catalog")


@router.post("/catalog/category")
def add_category(name: str = Form(...), description: str = Form(default=""), user=Depends(require_admin)):
    container = get_container()
    from uuid import uuid4

    container.catalog.add_category(Category(id=uuid4(), name=name.strip(), description=description.strip() or None))
    return _back("/admin/catalog")


@router.post("/catalog/service/{service_id}/active")
def toggle_service(service_id: UUID, active: str = Form(default="1"), user=Depends(require_admin)):
    get_container().catalog.set_service_active(service_id, active == "1")
    return _back("/admin/catalog")


@router.post("/catalog/sla")
def update_sla(
    priority: str = Form(...),
    response_hours: float = Form(...),
    resolution_hours: float = Form(...),
    escalation_hours: float = Form(...),
    user=Depends(require_admin),
):
    container = get_container()
    if min(response_hours, resolution_hours, escalation_hours) <= 0:
        raise ValidationError("SLA targets must be greater than zero.", field="response_hours")
    if response_hours >= resolution_hours:
        raise ValidationError("The response target must be shorter than the resolution target.", field="response_hours")
    container.catalog.save_sla_policy(
        SLAPolicy(
            priority=Priority(priority),
            response_hours=response_hours,
            resolution_hours=resolution_hours,
            escalation_hours=escalation_hours,
        )
    )
    container.audit.record(
        actor_id=user.id,
        action="SLA_POLICY_CHANGED",
        entity_type="sla_policy",
        entity_id=None,
        details={"description": f"{priority} SLA updated by {user.full_name}.", "actor_name": user.full_name},
    )
    return _back("/admin/catalog")
