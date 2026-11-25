import time
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["system"])

_started_at = time.monotonic()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    timestamp: datetime
    uptime_seconds: float


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check of the API process. Deliberately does not touch the database."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(time.monotonic() - _started_at, 3),
    )
