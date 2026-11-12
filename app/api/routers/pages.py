"""Server rendered pages.

Classic form posts and redirects rather than a single page application. The
reasons are in the report: it keeps authorisation on the server where it
belongs, it degrades without JavaScript, and it is honest about what this
application is, which is an internal operations tool rather than a product
site.

Every page handler does the same three things: build a query, ask a service,
render. No business logic lives here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.api.deps import get_container, get_current_user, get_optional_user, require_admin, require_technician
from app.core.exceptions import ITSMError, ValidationError
from app.domain.assignment import describe_strategies
from app.domain.enums import Impact, Priority, Role, SLAState, Status, Urgency
from app.domain.priority import PRIORITY_STRATEGIES
from app.domain.states import transition_graph
from app.repositories.base import IncidentQuery

router = APIRouter(tags=["pages"])


def _templates():
    from app.main import templates

    return templates


def _shell(request: Request, user) -> dict:
    """Context every signed in page needs: the nav rail and the bell."""
    container = get_container()
    return {
        "request": request,
        "user": user,
        "unread": container.notifications.unread_count(user.id) if user else 0,
        "settings": container.settings,
    }


def _query_from(request: Request, *, default_sort: str = "priority") -> IncidentQuery:
    params = request.query_params
    query = IncidentQuery(sort=params.get("sort") or default_sort)

    if text := (params.get("q") or "").strip():
        if text.upper().startswith("INC-"):
            query.reference = text
        else:
            query.text = text

    for value in params.getlist("status"):
        try:
            query.status.append(Status(value))
        except ValueError:
            continue
    for value in params.getlist("priority"):
        try:
            query.priority.append(Priority(value))
        except ValueError:
            continue

    if value := params.get("category"):
        try:
            query.category_id = UUID(value)
        except ValueError:
            pass
    if value := params.get("service"):
        try:
            query.service_id = UUID(value)
        except ValueError:
            pass
    if value := params.get("technician"):
        try:
            query.technician_id = UUID(value)
        except ValueError:
            pass
    if value := params.get("sla"):
        try:
            query.sla_state = SLAState(value)
        except ValueError:
            pass
    if days := params.get("days"):
        try:
            query.created_from = datetime.now(timezone.utc) - timedelta(days=int(days))
        except ValueError:
            pass

    query.open_only = params.get("open") == "1"
    query.unassigned_only = params.get("unassigned") == "1"
    try:
        query.offset = max(0, int(params.get("offset") or 0))
    except ValueError:
        query.offset = 0
    query.limit = 50
    return query


def _filter_options() -> dict:
    container = get_container()
    return {
        "all_statuses": list(Status),
        "all_priorities": list(Priority),
        "categories": container.catalog.list_categories(),
        "services": container.catalog.list_services(),
    }


# --- entry ---------------------------------------------------------------------


@router.get("/")
def root(user=Depends(get_optional_user)):
    return RedirectResponse(user.home_route() if user else "/signin", status_code=303)


@router.get("/signin")
def signin_page(request: Request, next: str = "", user=Depends(get_optional_user)):
    if user:
        return RedirectResponse(user.home_route(), status_code=303)
    return _templates().TemplateResponse(
        request=request, name="signin.html", context={"next": next, "error": None}
    )


@router.get("/signup")
def signup_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse(user.home_route(), status_code=303)
    return _templates().TemplateResponse(request=request, name="signup.html", context={"error": None})


# --- employee ---------------------------------------------------------------------


@router.get("/my-incidents")
def my_incidents(request: Request, user=Depends(get_current_user)):
    container = get_container()
    query = _query_from(request, default_sort="created")
    query.reporter_id = user.id
    incidents = container.incident_service.search_for(user, query)
    total = container.incident_service.count_for(user, IncidentQuery(reporter_id=user.id))

    awaiting = [i for i in incidents if i.status in (Status.PENDING, Status.RESOLVED)]
    open_count = len([i for i in incidents if i.is_open])

    return _templates().TemplateResponse(
        request=request,
        name="employee/my_incidents.html",
        context={
            **_shell(request, user),
            "incidents": incidents,
            "query": query,
            "stats": [
                ("Open", open_count),
                ("Needs your input", len(awaiting)),
                ("Reported in total", total),
            ],
            **_filter_options(),
        },
    )


@router.get("/report")
def report_form(request: Request, user=Depends(get_current_user)):
    container = get_container()
    return _templates().TemplateResponse(
        request=request,
        name="employee/report.html",
        context={
            **_shell(request, user),
            "services": container.catalog.list_services(),
            "categories": container.catalog.list_categories(),
            "impacts": list(Impact),
            "urgencies": list(Urgency),
            "form": {},
            "error": None,
        },
    )


@router.post("/report")
def submit_report(
    request: Request,
    title: str = Form(...),
    description: str = Form(default=""),
    service_id: str = Form(default=""),
    category_id: str = Form(default=""),
    impact: str = Form(default="MEDIUM"),
    urgency: str = Form(default="MEDIUM"),
    affected_users_count: str = Form(default="1"),
    user=Depends(get_current_user),
):
    container = get_container()
    form = {
        "title": title,
        "description": description,
        "service_id": service_id,
        "category_id": category_id,
        "impact": impact,
        "urgency": urgency,
        "affected_users_count": affected_users_count,
    }
    try:
        incident, duplicates = container.incident_service.report(
            reporter=user,
            title=title,
            description=description,
            service_id=UUID(service_id) if service_id else None,
            category_id=UUID(category_id) if category_id else None,
            impact=Impact(impact),
            urgency=Urgency(urgency),
            affected_users_count=int(affected_users_count or 1),
        )
    except (ITSMError, ValueError) as exc:
        message = exc.message if isinstance(exc, ITSMError) else "Check the values you entered."
        return _templates().TemplateResponse(
            request=request,
            name="employee/report.html",
            context={
                **_shell(request, user),
                "services": container.catalog.list_services(),
                "categories": container.catalog.list_categories(),
                "impacts": list(Impact),
                "urgencies": list(Urgency),
                "form": form,
                "error": message,
            },
            status_code=getattr(exc, "status_code", 422),
        )
    return RedirectResponse(f"/incidents/{incident.id}?created=1", status_code=303)


# --- incident detail, shared by all three roles -------------------------------------


@router.get("/incidents/{incident_id}")
def incident_detail(request: Request, incident_id: UUID, user=Depends(get_current_user)):
    container = get_container()
    service = container.incident_service
    incident = service.get_for(user, incident_id, with_updates=True)

    duplicate = None
    if incident.duplicate_of_id:
        try:
            duplicate = container.incidents.get(incident.duplicate_of_id)
        except ITSMError:
            duplicate = None

    context = {
        **_shell(request, user),
        "incident": incident,
        "updates": container.incidents.list_updates(incident.id),
        "actions": user.available_actions(incident),
        "duplicate": duplicate,
        "created": request.query_params.get("created") == "1",
        "risk": container.risk.assess(incident),
        "all_priorities": list(Priority),
    }

    if user.role is Role.TECHNICIAN:
        context["suggestions"] = service.suggest_resolutions(incident)
    if user.role is Role.ADMIN:
        context["recommendations"] = service.recommend_technicians(incident)
        context["technicians"] = container.users.list_technicians()

    return _templates().TemplateResponse(request=request, name="incident_detail.html", context=context)


@router.post("/incidents/{incident_id}/action")
def incident_action(
    request: Request,
    incident_id: UUID,
    action: str = Form(...),
    note: str = Form(default=""),
    rating: str = Form(default=""),
    technician_id: str = Form(default=""),
    priority: str = Form(default=""),
    user=Depends(get_current_user),
):
    container = get_container()
    service = container.incident_service

    if action == "assign":
        service.assign(
            actor=user,
            incident_id=incident_id,
            technician_id=UUID(technician_id) if technician_id else None,
        )
    elif action == "change_priority":
        if not priority:
            raise ValidationError("Pick a priority.", field="priority")
        service.perform  # keeps the authorisation funnel honest for readers
        service.change_priority(actor=user, incident_id=incident_id, priority=Priority(priority), reason=note)
    else:
        service.perform(
            actor=user,
            incident_id=incident_id,
            action_key=action,
            note=note,
            rating=int(rating) if rating else None,
            comment=note,
        )
    return RedirectResponse(f"/incidents/{incident_id}", status_code=303)


# --- technician ------------------------------------------------------------------------


@router.get("/queue")
def technician_queue(request: Request, user=Depends(require_technician)):
    container = get_container()
    tab = request.query_params.get("tab") or "mine"

    query = _query_from(request)
    if tab == "unassigned":
        query.unassigned_only = True
        query.technician_id = None
    elif tab == "all":
        query.technician_id = None
    else:
        query.technician_id = user.id

    incidents = container.incident_service.search_for(user, query)
    mine_open = container.incidents.count(IncidentQuery(technician_id=user.id, open_only=True))

    return _templates().TemplateResponse(
        request=request,
        name="technician/queue.html",
        context={
            **_shell(request, user),
            "incidents": incidents,
            "query": query,
            "tab": tab,
            "stats": [
                ("Assigned to me", mine_open),
                ("Capacity", f"{user.active_workload} of {user.max_workload}"),
                ("Resolved", user.resolved_count),
            ],
            **_filter_options(),
        },
    )


# --- administrator ------------------------------------------------------------------------


@router.get("/operations")
def operations(request: Request, user=Depends(require_admin)):
    container = get_container()
    reporting = container.reporting
    overview = reporting.overview()

    return _templates().TemplateResponse(
        request=request,
        name="admin/operations.html",
        context={
            **_shell(request, user),
            "overview": overview,
            "workload": reporting.technician_workload(),
            "services": reporting.service_analysis(),
            "categories": reporting.category_analysis(),
            "breaches": reporting.sla_breaches(),
            "at_risk": reporting.at_risk(),
            "clusters": container.incident_service.correlated_clusters(),
            "audit": container.audit.recent(limit=12),
            "priority_mix": reporting.priority_mix(),
            "feedback": reporting.feedback_summary(),
        },
    )


@router.get("/admin/incidents")
def admin_incidents(request: Request, user=Depends(require_admin)):
    container = get_container()
    query = _query_from(request)
    incidents = container.incident_service.search_for(user, query)
    return _templates().TemplateResponse(
        request=request,
        name="admin/incidents.html",
        context={
            **_shell(request, user),
            "incidents": incidents,
            "query": query,
            "total": container.incidents.count(query),
            "technicians": container.users.list_technicians(),
            **_filter_options(),
        },
    )


@router.get("/admin/people")
def admin_people(request: Request, user=Depends(require_admin)):
    container = get_container()
    return _templates().TemplateResponse(
        request=request,
        name="admin/people.html",
        context={
            **_shell(request, user),
            "people": container.users.list_all(),
            "workload": container.reporting.technician_workload(),
            "categories": container.catalog.list_categories(),
            "roles": [r for r in Role],
        },
    )


@router.get("/admin/catalog")
def admin_catalog(request: Request, user=Depends(require_admin)):
    container = get_container()
    return _templates().TemplateResponse(
        request=request,
        name="admin/catalog.html",
        context={
            **_shell(request, user),
            "services": container.catalog.list_services(active_only=False),
            "categories": container.catalog.list_categories(),
            "policies": container.catalog.list_sla_policies(),
        },
    )


@router.get("/admin/settings")
def admin_settings(request: Request, user=Depends(require_admin)):
    container = get_container()
    return _templates().TemplateResponse(
        request=request,
        name="admin/settings.html",
        context={
            **_shell(request, user),
            "assignment_strategies": describe_strategies(),
            "priority_strategies": [
                {"name": s.name, "label": s.name.title(), "description": s.description}
                for s in PRIORITY_STRATEGIES.values()
            ],
            "channels": container.notification_service.channels,
            "graph": transition_graph(),
        },
    )


@router.get("/admin/audit")
def admin_audit(request: Request, user=Depends(require_admin)):
    container = get_container()
    return _templates().TemplateResponse(
        request=request,
        name="admin/audit.html",
        context={**_shell(request, user), "entries": container.audit.recent(limit=200)},
    )


# --- notifications --------------------------------------------------------------------------


@router.get("/notifications")
def notifications_page(request: Request, user=Depends(get_current_user)):
    container = get_container()
    items = container.notifications.list_for_user(user.id, limit=50)
    container.notifications.mark_all_read(user.id)
    return _templates().TemplateResponse(
        request=request,
        name="notifications.html",
        context={**_shell(request, user), "items": items, "unread": 0},
    )
