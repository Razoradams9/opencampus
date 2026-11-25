import uuid

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import AppSettings, CurrentPrincipal, DbSession, verify_csrf
from app.api.rate_limits import LoginGuard, guard_refresh, guard_register
from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import new_opaque_token
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    SessionOut,
    SwitchInstitutionRequest,
    TokenResponse,
)
from app.services import auth as auth_service
from app.services.auth import IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_PATH = "/api/auth"  # refresh token is sent only to auth endpoints


def _set_auth_cookies(response: Response, settings: Settings, refresh_token: str) -> None:
    common = {"secure": settings.cookie_secure, "samesite": settings.cookie_samesite}
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh_token,
        max_age=settings.refresh_token_ttl,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        **common,
    )
    # Readable by the frontend so it can echo it in X-CSRF-Token.
    response.set_cookie(
        settings.csrf_cookie_name, new_opaque_token(), max_age=settings.refresh_token_ttl, path="/", httponly=False, **common
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    common = {"secure": settings.cookie_secure, "samesite": settings.cookie_samesite}
    response.delete_cookie(settings.refresh_cookie_name, path=REFRESH_COOKIE_PATH, httponly=True, **common)
    response.delete_cookie(settings.csrf_cookie_name, path="/", **common)


def _token_response(db: DbSession, settings: Settings, response: Response, tokens: IssuedTokens) -> TokenResponse:
    _set_auth_cookies(response, settings, tokens.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.access_token_ttl,
        me=auth_service.build_me(db, tokens.session.user, tokens.session),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def register(body: RegisterRequest, request: Request, response: Response, db: DbSession, settings: AppSettings):
    guard_register(request, settings)  # before password hashing and account creation
    tokens = auth_service.register(db, settings, body, request.headers.get("user-agent"))
    return _token_response(db, settings, response, tokens)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession, settings: AppSettings):
    guard = LoginGuard(request, settings, body.email)
    guard.before_attempt()
    try:
        tokens = auth_service.login(db, settings, body, request.headers.get("user-agent"))
    except ApiError as error:
        if error.code == "invalid_credentials":  # unknown email and wrong password alike
            guard.record_failure()
        raise
    guard.record_success()
    return _token_response(db, settings, response, tokens)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(verify_csrf)])
def refresh(request: Request, response: Response, db: DbSession, settings: AppSettings):
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    guard_refresh(request, db, settings, raw_token)
    tokens = auth_service.rotate_refresh_token(db, settings, raw_token)
    return _token_response(db, settings, response, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_csrf)])
def logout(request: Request, db: DbSession, settings: AppSettings) -> Response:
    auth_service.logout(db, request.cookies.get(settings.refresh_cookie_name))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(response, settings)
    return response


@router.get("/me", response_model=MeResponse)
def me(principal: CurrentPrincipal, db: DbSession):
    return auth_service.build_me(db, principal.user, principal.session)


@router.post("/switch-institution", response_model=MeResponse)
def switch_institution(body: SwitchInstitutionRequest, principal: CurrentPrincipal, db: DbSession):
    auth_service.switch_institution(db, principal.session, body.institution_id)
    return auth_service.build_me(db, principal.user, principal.session)


@router.get("/sessions", response_model=list[SessionOut])
def sessions(principal: CurrentPrincipal, db: DbSession):
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            user_agent=s.user_agent,
            current=s.id == principal.session.id,
        )
        for s in auth_service.list_sessions(db, principal.user.id)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(session_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession) -> Response:
    auth_service.revoke_session(db, principal.user.id, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
