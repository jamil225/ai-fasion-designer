import logging
from datetime import datetime, timezone, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 3600  # 1 hour


def verify_google_id_token(credential: str, google_client_id: str) -> dict:
    """Verify a Google ID token and return user info (email, name, picture).

    Called once during login, not on every request.
    """
    try:
        id_info = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            google_client_id,
        )
        return {
            "email": id_info["email"],
            "name": id_info.get("name", ""),
            "picture": id_info.get("picture", ""),
        }
    except ValueError as e:
        logger.warning("Google token verification failed (ValueError): %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")
    except Exception as e:
        logger.warning("Google token verification failed (%s): %s", type(e).__name__, e)
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")


def create_session_token(user_info: dict, session_secret: str) -> str:
    """
    Create a short-lived signed session token containing user profile information.
    
    Parameters:
        user_info (dict): User data containing `email`, `name`, and `picture`.
        session_secret (str): Secret used to sign the token.
    
    Returns:
        str: The encoded JWT session token.
    """
    payload = {
        "email": user_info["email"],
        "name": user_info["name"],
        "picture": user_info["picture"],
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=SESSION_MAX_AGE_SECONDS),
    }
    token = jwt.encode(payload, session_secret, algorithm="HS256")
    logger.info("Session token created for user=%s", user_info["email"])
    return token


def verify_session_token(token: str, session_secret: str) -> dict:
    """
    Verify a signed session token and extract its user information.
    
    Parameters:
        token (str): The signed session JWT to verify.
        session_secret (str): Secret used to verify the token signature.
    
    Returns:
        dict | None: User information containing the email, name, and picture when
            the token is valid; `None` if the token is expired or invalid.
    """
    try:
        payload = jwt.decode(token, session_secret, algorithms=["HS256"])
        return {
            "email": payload["email"],
            "name": payload.get("name", ""),
            "picture": payload.get("picture", ""),
        }
    except jwt.ExpiredSignatureError:
        logger.info("Session token expired")
        return None
    except jwt.InvalidTokenError:
        logger.info("Session token invalid")
        return None


async def verify_auth(
    request: Request,
    api_key: str | None = Security(API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Authenticate a request using a session cookie or API key.
    
    Returns:
    	str: The authenticated user's email or ``"api-key-user"``.
    
    Raises:
    	HTTPException: If neither authentication method succeeds.
    """
    # 1. Try HttpOnly session cookie
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token and settings.session_secret:
        user_info = verify_session_token(session_token, settings.session_secret)
        if user_info:
            logger.info("Auth OK via session cookie, user=%s", user_info["email"])
            return user_info["email"]

    # 2. Fall back to API key (for Swagger / programmatic access)
    if api_key and api_key == settings.app_api_key:
        logger.info("Auth OK via API key")
        return "api-key-user"

    logger.warning("Auth FAILED — no valid session or API key")
    raise HTTPException(status_code=401, detail="Authentication required")


async def verify_admin(
    request: Request,
    api_key: str | None = Security(API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> str:
    """Require admin privileges for destructive operations.

    Grants access if:
      - The request carries a valid ADMIN_API_KEY, or
      - The session user's email is in ADMIN_EMAILS.

    Returns the admin identifier (email or 'admin-api-key-user').
    """
    # 1. Dedicated admin API key (highest priority)
    if api_key and settings.admin_api_key and api_key == settings.admin_api_key:
        logger.info("Admin auth OK via admin API key")
        return "admin-api-key-user"

    # 2. Session cookie — check if user email is in the admin list
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token and settings.session_secret:
        user_info = verify_session_token(session_token, settings.session_secret)
        if user_info and user_info["email"] in settings.admin_emails:
            logger.info("Admin auth OK via session, user=%s", user_info["email"])
            return user_info["email"]

    logger.warning("Admin auth FAILED — insufficient privileges")
    raise HTTPException(status_code=403, detail="Admin privileges required")
