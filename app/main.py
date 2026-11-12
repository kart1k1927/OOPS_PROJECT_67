"""Application entry point.

Wires the layers together and nothing else. Three things worth noting:

  Exception handling is centralised. Every ITSMError subclass carries its own
  status code, so one handler covers the whole family and returns JSON to an
  API caller or a rendered page to a browser.

  SLA monitoring runs as a background task started in the lifespan, which is
  what makes the monitoring continuous rather than something a cron job was
  supposed to do.

  Templates get their formatting helpers from app/api/presenters.py.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import presenters
from app.api.deps import get_container, get_optional_user
from app.core.config import BASE_DIR, get_settings
from app.core.exceptions import AuthenticationError, ITSMError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("itsm")

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))
presenters.register(templates)

SLA_SWEEP_SECONDS = 60


async def _sla_monitor() -> None:
    """Continuous SLA monitoring. Replaces the never scheduled
    refresh_incident_sla_breaches() the schema shipped with.

    Built on its own Supabase client so the sweep's burst of reads and writes
    does not share a connection pool with request handling. See
    app/database/database.py:make_client for why that matters.
    """
    from app.database.database import make_client
    from app.services.container import build_container

    try:
        container = await asyncio.to_thread(lambda: build_container(make_client()))
    except Exception:
        logger.exception("SLA monitor could not start, continuing without it")
        return

    while True:
        await asyncio.sleep(SLA_SWEEP_SECONDS)
        try:
            await asyncio.to_thread(container.sla_service.sweep)
        except Exception:
            logger.exception("SLA sweep failed, continuing")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_sla_monitor())
    logger.info("SLA monitor started, sweeping every %ss", SLA_SWEEP_SECONDS)
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="I-ITSM",
    description="Intelligent IT Service Management and Incident Resolution System",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

from app.api.routers import admin, auth, incidents, pages, technicians  # noqa: E402

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(incidents.router)
app.include_router(technicians.router)
app.include_router(admin.router)


def _wants_json(request: Request) -> bool:
    if request.url.path.startswith("/api/"):
        return True
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


@app.exception_handler(ITSMError)
async def handle_itsm_error(request: Request, exc: ITSMError):
    """One handler for every deliberate error in the system."""
    if isinstance(exc, AuthenticationError) and not _wants_json(request):
        return RedirectResponse(f"/signin?next={request.url.path}", status_code=303)

    if _wants_json(request):
        return JSONResponse(exc.to_dict(), status_code=exc.status_code)

    logger.info("%s on %s: %s", exc.code, request.url.path, exc.message)
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "user": get_optional_user(request),
            "code": exc.status_code,
            "heading": exc.code.replace("_", " ").capitalize(),
            "message": exc.message,
        },
        status_code=exc.status_code,
    )


@app.exception_handler(404)
async def handle_404(request: Request, exc):
    if _wants_json(request):
        return JSONResponse({"error": "not_found", "message": "No such endpoint."}, status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "user": get_optional_user(request),
            "code": 404,
            "heading": "Page not found",
            "message": "That address does not exist in this application.",
        },
        status_code=404,
    )


@app.get("/health", include_in_schema=False)
def health_check():
    container = get_container()
    try:
        container.catalog.list_categories()
    except Exception as exc:
        return JSONResponse({"status": "degraded", "database": str(exc)[:200]}, status_code=503)
    return {
        "status": "ok",
        "database": "connected",
        "assignment_strategy": container.settings.assignment_strategy_name,
        "priority_strategy": container.settings.priority_strategy_name,
        "notification_channels": [c.name for c in container.notification_service.channels],
    }
