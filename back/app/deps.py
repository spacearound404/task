from fastapi import Header, HTTPException, status
from typing import Dict, Any, Optional

from .core.security import decode_access_token
from .core.config import get_settings


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    settings = get_settings()
    if not authorization:
        if settings.allow_anon:
            return {"id": None, "is_anon": True}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        if settings.allow_anon:
            return {"id": None, "is_anon": True}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")

    token = parts[1]
    payload = decode_access_token(token)

    user = payload.get("user")
    if not isinstance(user, dict):
        if settings.allow_anon:
            return {"id": None, "is_anon": True}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return user

