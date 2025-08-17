from fastapi import Header, HTTPException, status
from typing import Dict, Any, Optional

from .core.security import decode_access_token


def get_current_user(_authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not _authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    parts = _authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")

    token = parts[1]
    payload = decode_access_token(token)

    user = payload.get("user")
    if not isinstance(user, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return user

