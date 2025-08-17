from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..deps import get_current_user
from ..models import Task


router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=List[Task])
def list_events(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    stmt = select(Task).where(((Task.owner_id == owner_id) | (Task.owner_id.is_(None))) & (Task.kind == "event"))
    if start is not None:
        stmt = stmt.where(Task.event_end >= start)
    if end is not None:
        stmt = stmt.where(Task.event_start <= end)
    return session.exec(stmt).all()


@router.post("/", response_model=Task)
def create_event(event: Task, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    event.id = None
    event.kind = "event"
    event.owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    # coerce ISO strings
    if isinstance(event.event_start, str) and event.event_start:
        try:
            s = event.event_start.replace("Z", "+00:00")
            event.event_start = datetime.fromisoformat(s)
        except Exception:
            event.event_start = None
    if isinstance(event.event_end, str) and event.event_end:
        try:
            s = event.event_end.replace("Z", "+00:00")
            event.event_end = datetime.fromisoformat(s)
        except Exception:
            event.event_end = None
    if not event.event_start or not event.event_end:
        raise HTTPException(status_code=400, detail="event_start and event_end are required")
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


