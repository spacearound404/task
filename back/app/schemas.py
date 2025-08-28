from pydantic import BaseModel
from typing import Any, Dict, Optional


class AuthRequest(BaseModel):
    init_data: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserModel(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class MeResponse(BaseModel):
    user: Dict[str, Any]


class AiSettingsUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None

