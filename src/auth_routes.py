import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.auth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    verify_google_id_token,
    verify_session_token,
)
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class GoogleLoginRequest(BaseModel):
    credential: str


@router.post("/google")
async def login_with_google(
    body: GoogleLoginRequest,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Verify Google ID token and set HttpOnly session cookie."""
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="Google Client ID not configured")

    logger.info("Login attempt — client_id=%s..., credential_len=%d",
                settings.google_client_id[:20], len(body.credential))
    user_info = verify_google_id_token(body.credential, settings.google_client_id)
    session_token = create_session_token(user_info, settings.session_secret)

    response = JSONResponse(content={
        "email": user_info["email"],
        "name": user_info["name"],
        "picture": user_info["picture"],
    })

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="strict",
        secure=False,  # Set True in production (requires HTTPS)
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )

    logger.info("User logged in: %s", user_info["email"])
    return response


@router.get("/me")
async def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Return current user info from session cookie, or 401."""
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token or not settings.session_secret:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_info = verify_session_token(session_token, settings.session_secret)
    if not user_info:
        raise HTTPException(status_code=401, detail="Session expired")

    return {
        "email": user_info["email"],
        "name": user_info["name"],
        "picture": user_info["picture"],
    }


@router.post("/logout")
async def logout() -> JSONResponse:
    """Clear the session cookie."""
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
    )
    return response
