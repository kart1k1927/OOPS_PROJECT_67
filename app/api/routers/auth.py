"""Registration, sign in, sign out.

Form posts rather than a JSON API, because every one of these is a browser
form. The session is an HttpOnly cookie, so page scripts cannot read the token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.api.deps import get_container, get_current_user
from app.core.exceptions import ITSMError, ValidationError
from app.core.security import SESSION_COOKIE
from app.domain.enums import Role

router = APIRouter(tags=["auth"])


def _session_response(user, container, *, next_url: str | None = None) -> RedirectResponse:
    token = container.auth.token_for(user)
    destination = next_url if next_url and next_url.startswith("/") else user.home_route()
    response = RedirectResponse(destination, status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,
        path="/",
    )
    return response


@router.post("/signin")
def sign_in(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(default=""),
):
    container = get_container()
    try:
        user = container.auth.authenticate(email=email, password=password)
    except ITSMError as exc:
        from app.main import templates

        return templates.TemplateResponse(
            request=request,
            name="signin.html",
            context={"error": exc.message, "email": email, "next": next},
            status_code=exc.status_code,
        )
    return _session_response(user, container, next_url=next)


@router.post("/signup")
def sign_up(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(default=""),
):
    container = get_container()
    try:
        if confirm and password != confirm:
            raise ValidationError("The two passwords do not match.", field="confirm")
        user = container.auth.register(full_name=full_name, email=email, password=password, role=Role.EMPLOYEE)
    except ITSMError as exc:
        from app.main import templates

        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": exc.message, "full_name": full_name, "email": email},
            status_code=exc.status_code,
        )
    return _session_response(user, container)


@router.post("/signout")
@router.get("/signout")
def sign_out():
    response = RedirectResponse("/signin", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.post("/account/password")
def change_password(
    current: str = Form(...),
    replacement: str = Form(...),
    user=Depends(get_current_user),
):
    get_container().auth.set_password(user, current=current, replacement=replacement)
    return RedirectResponse(user.home_route(), status_code=303)
