from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Error with a stable machine-readable code: {"detail": ..., "code": ...}."""

    def __init__(self, status: int, code: str, message: str, headers: dict[str, str] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def unauthorized(code: str = "not_authenticated", message: str = "Authentication required") -> ApiError:
    return ApiError(401, code, message, {"WWW-Authenticate": "Bearer"})


def forbidden(code: str, message: str) -> ApiError:
    return ApiError(403, code, message)


async def api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status, headers=exc.headers)
