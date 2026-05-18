from __future__ import annotations

import secrets

from fastapi import Cookie, Response

from app.core.config import get_settings


def get_anonymous_client_id(
    response: Response,
    chiron_client_id: str | None = Cookie(default=None),
) -> str:
    if chiron_client_id:
        return chiron_client_id

    settings = get_settings()
    client_id = secrets.token_urlsafe(24)
    response.set_cookie(
        key=settings.anonymous_client_cookie_name,
        value=client_id,
        httponly=True,
        samesite="lax",
        secure=settings.environment != "development",
        max_age=settings.anonymous_client_cookie_max_age_seconds,
        path="/",
    )
    return client_id
