from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..schemas import MeResponse


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=MeResponse)
def me(current_user=Depends(get_current_user)):
    return {"user": current_user}

