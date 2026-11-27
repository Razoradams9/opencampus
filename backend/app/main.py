from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import academic, auth, health, institutions, platform
from app.core.config import get_settings
from app.core.errors import ApiError, api_error_handler


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast if required configuration is missing
    app = FastAPI(title=settings.app_name, version=settings.version)

    # Only needed when the UI is served from a different origin than the API.
    # In development the Vite proxy makes them same-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    app.add_exception_handler(ApiError, api_error_handler)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(institutions.public_router, prefix="/api")
    app.include_router(institutions.tenant_router, prefix="/api")
    app.include_router(platform.router, prefix="/api")
    app.include_router(academic.router, prefix="/api")
    return app


app = create_app()
