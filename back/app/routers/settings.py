from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..deps import get_current_user
from ..models import UserSettings, AiSettings
from ..schemas import AiSettingsUpdate


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



@router.get("/ai", response_model=AiSettings)
def get_ai_settings(session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    effective_owner_id = owner_id if owner_id is not None else 0
    settings = session.exec(select(AiSettings).where(AiSettings.owner_id == effective_owner_id)).first()
    if not settings:
        settings = AiSettings(owner_id=effective_owner_id)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@router.put("/ai", response_model=AiSettings)
def update_ai_settings(update: AiSettingsUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    effective_owner_id = owner_id if owner_id is not None else 0
    settings = session.exec(select(AiSettings).where(AiSettings.owner_id == effective_owner_id)).first()
    if not settings:
        settings = AiSettings(owner_id=effective_owner_id)
        session.add(settings)
    data = update.dict(exclude_unset=True)
    data.pop("id", None)
    data.pop("owner_id", None)
    # normalize: trim and ignore empty string to avoid wiping key unintentionally
    if "openai_api_key" in data:
        v = data.get("openai_api_key")
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                data.pop("openai_api_key", None)
            else:
                data["openai_api_key"] = v
    for k, v in data.items():
        setattr(settings, k, v)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings

