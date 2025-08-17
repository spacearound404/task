from fastapi import APIRouter

from ..core.security import create_access_token, verify_telegram_webapp_data
from ..schemas import AuthRequest, AuthResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=AuthResponse)
def auth_telegram(req: AuthRequest):
    verified = verify_telegram_webapp_data(req.init_data)
    user = verified.get("user") or {}

    token = create_access_token({"user": user})
    return AuthResponse(access_token=token, user=user)

