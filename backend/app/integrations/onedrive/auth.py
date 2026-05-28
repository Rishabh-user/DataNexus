from datetime import datetime, timedelta, timezone

import msal

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

AUTHORITY = f"https://login.microsoftonline.com/{settings.ms_tenant_id}"
# offline_access, openid, profile are reserved by MSAL and added automatically
_RESERVED = {"offline_access", "openid", "profile"}
GRAPH_SCOPES = [
    f"https://graph.microsoft.com/{s}" for s in settings.ms_scopes_list if s not in _RESERVED
]


def _get_msal_app() -> msal.PublicClientApplication:
    return msal.PublicClientApplication(
        client_id=settings.ms_client_id,
        authority=AUTHORITY,
    )


def get_auth_url(state: str | None = None) -> str:
    app = _get_msal_app()
    result = app.get_authorization_request_url(
        scopes=GRAPH_SCOPES,
        redirect_uri=settings.ms_redirect_uri,
        state=state,
    )
    return result


def exchange_code_for_tokens(code: str) -> dict:
    app = _get_msal_app()
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=GRAPH_SCOPES,
        redirect_uri=settings.ms_redirect_uri,
    )

    if "error" in result:
        logger.error("Token exchange failed: %s", result.get("error_description"))
        raise ValueError(f"Token exchange failed: {result.get('error_description')}")

    expires_in = result.get("expires_in", 3600)
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        "scopes": " ".join(result.get("scope", [])),
    }


def refresh_access_token(refresh_token: str) -> dict:
    app = _get_msal_app()
    result = app.acquire_token_by_refresh_token(
        refresh_token=refresh_token,
        scopes=GRAPH_SCOPES,
    )

    if "error" in result:
        logger.error("Token refresh failed: %s", result.get("error_description"))
        raise ValueError(f"Token refresh failed: {result.get('error_description')}")

    expires_in = result.get("expires_in", 3600)
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", refresh_token),
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
