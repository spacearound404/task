from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..deps import get_current_user
from ..models import UserSettings


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/me", response_model=UserSettings)
def get_my_settings(session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    settings = session.exec(select(UserSettings).where(UserSettings.owner_id == owner_id)).first()
    if not settings:
        settings = UserSettings(owner_id=owner_id or 0)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@router.put("/me", response_model=UserSettings)
def update_my_settings(update: UserSettings, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    settings = session.exec(select(UserSettings).where(UserSettings.owner_id == owner_id)).first()
    if not settings:
        settings = UserSettings(owner_id=owner_id or 0)
        session.add(settings)
    data = update.dict(exclude_unset=True)
    data.pop("id", None)
    data.pop("owner_id", None)
    for k, v in data.items():
        setattr(settings, k, v)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


