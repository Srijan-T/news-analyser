import asyncio
import hmac

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.auth import COOKIE_NAME, SESSION_TTL_SECONDS, sign_session, verify_session
from app.config import Settings
from app.errors import AppError

router = APIRouter(prefix="/auth", tags=["auth"])

FAILED_LOGIN_DELAY_SECONDS = 0.5  # slows down password guessing


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class SessionResponse(BaseModel):
    auth_required: bool
    authenticated: bool


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/session", response_model=SessionResponse, summary="Am I signed in?")
def session(request: Request) -> SessionResponse:
    settings = _settings(request)
    if settings.app_password is None or settings.session_secret is None:
        return SessionResponse(auth_required=False, authenticated=True)
    token = request.cookies.get(COOKIE_NAME)
    return SessionResponse(
        auth_required=True,
        authenticated=verify_session(settings.session_secret.get_secret_value(), token),
    )


@router.post(
    "/login",
    status_code=204,
    summary="Sign in with the shared password",
    responses={401: {"description": "Wrong password"}},
)
async def login(body: LoginRequest, request: Request, response: Response) -> None:
    settings = _settings(request)
    if settings.app_password is None or settings.session_secret is None:
        return  # sign-in disabled: nothing to do
    expected = settings.app_password.get_secret_value().encode()
    if not hmac.compare_digest(body.password.encode(), expected):
        # Awaited, not time.sleep: a blocking sleep would hold one of the shared worker
        # threads per wrong guess, so parallel guesses could stall every other request.
        await asyncio.sleep(FAILED_LOGIN_DELAY_SECONDS)
        raise AppError(401, "invalid_password", "That password isn't right")
    response.set_cookie(
        COOKIE_NAME,
        sign_session(settings.session_secret.get_secret_value()),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,  # not readable from JavaScript
        secure=settings.app_env == "production",  # HTTPS-only on Railway
        samesite="lax",  # not sent on cross-site POSTs
    )


@router.post("/logout", status_code=204, summary="Sign out")
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)
