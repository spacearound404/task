import hashlib
import hmac
import json
import time
from typing import Any, Dict
from urllib.parse import parse_qsl

import jwt
from fastapi import HTTPException, status

from .config import get_settings


def _compute_telegram_webapp_hash(init_data: str, bot_token: str) -> str:
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    return hmac.new(secret_key, init_data.encode(), hashlib.sha256).hexdigest()


def verify_telegram_webapp_data(init_data: str) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN is not configured")

    try:
        # Parse URL-encoded query string into decoded key-value pairs
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        data = dict(pairs)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid initData format")

    hash_from_tg = data.pop("hash", None)
    if not hash_from_tg:
        raise HTTPException(status_code=400, detail="Missing hash in initData")

    # Telegram requires data-check-string: keys sorted, joined as key=value\n
    lines = []
    for key in sorted(data.keys()):
        lines.append(f"{key}={data[key]}")
    data_check_string = "\n".join(lines)

    computed = _compute_telegram_webapp_hash(data_check_string, settings.telegram_bot_token)
    if not hmac.compare_digest(computed, hash_from_tg):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    # Optional: check auth_date is recent (e.g., 1 day)
    auth_date_str = data.get("auth_date")
    if auth_date_str:
        try:
            auth_ts = int(auth_date_str)
            if time.time() - auth_ts > 60 * 60 * 24:
                raise HTTPException(status_code=401, detail="Expired initData")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid auth_date")

    user_json = data.get("user")
    user_obj: Dict[str, Any] = {}
    if user_json:
        try:
            # Value already URL-decoded by parse_qsl
            user_obj = json.loads(user_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid user payload")

    return {"raw": data, "user": user_obj}


def create_access_token(payload: Dict[str, Any], expires_in_seconds: int = 60 * 60 * 24 * 7) -> str:
    settings = get_settings()
    to_encode = payload.copy()
    to_encode["exp"] = int(time.time()) + expires_in_seconds
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

