from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings


def create_access_token(*, user_id: str, username: str, is_admin: bool) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "username": username,
        "is_admin": is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, settings.app_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.app_secret, algorithms=["HS256"])
