from datetime import date
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func

from ..db import get_session
from ..deps import get_current_user
from ..models import Task


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def stats_summary(session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    total = session.exec(select(func.count()).select_from(Task).where((Task.owner_id == owner_id) | (Task.owner_id.is_(None)))).one()
    overdue = session.exec(select(func.count()).select_from(Task).where(Task.deadline < date.today())).one()
    return {"total": total, "overdue": overdue}


