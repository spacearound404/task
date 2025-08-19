import hashlib
import hmac
import json
import time
from typing import Any, Dict
from urllib.parse import parse_qsl

import jwt
from fastapi import HTTPException, status
from init_data_py import InitData

from .config import get_settings


def _compute_telegram_webapp_hash(init_data: str, bot_token: str) -> str:
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    return hmac.new(secret_key, init_data.encode(), hashlib.sha256).hexdigest()


def verify_telegram_webapp_data(init_data: str) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN is not configured")

    # Parse and validate using init-data-py
    try:
        parsed = InitData.parse(init_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid initData format")

    try:
        is_valid = parsed.validate(bot_token=settings.telegram_bot_token, lifetime=60 * 60 * 24)
    except Exception:
        is_valid = False

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    # Extract user info
    user_obj: Dict[str, Any] = {}
    user_attr = getattr(parsed, "user", None)
    try:
        if user_attr is not None:
            if hasattr(user_attr, "model_dump"):
                user_obj = user_attr.model_dump()
            elif hasattr(user_attr, "dict"):
                user_obj = user_attr.dict()  # type: ignore[assignment]
    except Exception:
        user_obj = {}

    # Raw map for completeness
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        raw_map = dict(pairs)
    except Exception:
        raw_map = {}

    return {"raw": raw_map, "user": user_obj}


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

