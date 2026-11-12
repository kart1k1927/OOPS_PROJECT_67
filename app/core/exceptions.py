"""Application exception hierarchy.

One base class so the API layer can translate the whole family in a single
handler, and so no domain code ever raises a bare ValueError. Each subclass
carries the HTTP status it means and a stable machine readable code, but the
domain itself never imports FastAPI: the status code is just an integer
attribute, and the mapping is applied at the edge.

The message is written for the person reading it. "Cannot close an incident
that is not resolved" tells a technician what to do next. "Invalid state
transition" does not.
"""

from __future__ import annotations


class ITSMError(Exception):
    """Base for every error this application raises deliberately."""

    status_code: int = 400
    code: str = "itsm_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}


# --- authentication and authorisation ---------------------------------------


class AuthenticationError(ITSMError):
    status_code = 401
    code = "authentication_failed"


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"

    def __init__(self, message: str = "Email or password is incorrect.") -> None:
        super().__init__(message)


class InactiveAccountError(AuthenticationError):
    code = "inactive_account"

    def __init__(self, message: str = "This account has been deactivated. Contact an administrator.") -> None:
        super().__init__(message)


class UnauthorizedOperationError(ITSMError):
    status_code = 403
    code = "unauthorized_operation"


# --- not found ---------------------------------------------------------------


class NotFoundError(ITSMError):
    status_code = 404
    code = "not_found"


class IncidentNotFoundError(NotFoundError):
    code = "incident_not_found"

    def __init__(self, incident_ref: str) -> None:
        super().__init__(f"Incident {incident_ref} does not exist.", details={"incident": incident_ref})


class UserNotFoundError(NotFoundError):
    code = "user_not_found"

    def __init__(self, user_ref: str) -> None:
        super().__init__(f"User {user_ref} does not exist.", details={"user": user_ref})


class ServiceNotFoundError(NotFoundError):
    code = "service_not_found"

    def __init__(self, service_ref: str) -> None:
        super().__init__(f"IT service {service_ref} does not exist or is not active.", details={"service": service_ref})


class CategoryNotFoundError(NotFoundError):
    code = "category_not_found"

    def __init__(self, category_ref: str) -> None:
        super().__init__(f"Category {category_ref} does not exist.", details={"category": category_ref})


# --- conflicts and business rules --------------------------------------------


class ConflictError(ITSMError):
    status_code = 409
    code = "conflict"


class InvalidStateTransitionError(ConflictError):
    code = "invalid_state_transition"

    def __init__(self, current, target, *, hint: str | None = None) -> None:
        current_label = getattr(current, "value", current)
        target_label = getattr(target, "value", target)
        message = f"An incident that is {current_label} cannot move to {target_label}."
        if hint:
            message = f"{message} {hint}"
        super().__init__(message, details={"current_status": current_label, "target_status": target_label})


class DuplicateIncidentError(ConflictError):
    code = "duplicate_incident"

    def __init__(self, existing_ref: str) -> None:
        super().__init__(
            f"This looks like a duplicate of {existing_ref}. Add a note there instead, or submit anyway.",
            details={"duplicate_of": existing_ref},
        )


class EmailAlreadyRegisteredError(ConflictError):
    code = "email_already_registered"

    def __init__(self, email: str) -> None:
        super().__init__(f"An account already exists for {email}.", details={"email": email})


class TechnicianUnavailableError(ConflictError):
    code = "technician_unavailable"

    def __init__(self, message: str = "No active technician is available to take this incident.") -> None:
        super().__init__(message)


class WorkloadExceededError(ConflictError):
    code = "workload_exceeded"

    def __init__(self, technician_ref: str, active: int, ceiling: int) -> None:
        super().__init__(
            f"{technician_ref} is already handling {active} incidents, the limit is {ceiling}.",
            details={"technician": technician_ref, "active": active, "max": ceiling},
        )


class SLAPolicyMissingError(ConflictError):
    code = "sla_policy_missing"

    def __init__(self, priority: str) -> None:
        super().__init__(
            f"No SLA policy is configured for priority {priority}. An administrator must add one.",
            details={"priority": priority},
        )


# --- input and infrastructure -------------------------------------------------


class ValidationError(ITSMError):
    status_code = 422
    code = "validation_error"

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message, details={"field": field} if field else {})


class RepositoryError(ITSMError):
    """A persistence call failed. Wraps the driver's exception so that no
    supabase or httpx type ever escapes the repository layer."""

    status_code = 503
    code = "storage_unavailable"

    def __init__(self, message: str = "The incident database could not be reached. Try again in a moment.") -> None:
        super().__init__(message)
