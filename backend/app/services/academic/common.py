from sqlalchemy.exc import IntegrityError

from app.core.errors import ApiError


def constraint_name(exc: IntegrityError) -> str | None:
    """Name of the violated constraint, from psycopg's diagnostics."""
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def not_found(kind: str, label: str) -> ApiError:
    # Records of other institutions are indistinguishable from missing ones.
    return ApiError(404, f"{kind}_not_found", f"{label} not found")


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)
