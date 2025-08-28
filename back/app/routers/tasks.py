from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..deps import get_current_user
from ..models import Task, TaskUpdate


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=List[Task])
def list_tasks(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
    project_id: Optional[int] = None,
    day: Optional[date] = Query(default=None, description="Filter by deadline date"),
):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    statement = select(Task).where((Task.owner_id == owner_id) | (Task.owner_id.is_(None)))
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    if day is not None:
        statement = statement.where(Task.deadline == day)
    statement = statement.order_by(Task.created_at.desc())
    return session.exec(statement).all()


def _coerce_task_types(task: Task) -> None:
    # Accept ISO strings from client and coerce to native types
    if isinstance(task.deadline, str) and task.deadline:
        try:
            task.deadline = date.fromisoformat(task.deadline)
        except Exception:
            task.deadline = None
    if isinstance(task.event_start, str) and task.event_start:
        try:
            s = task.event_start.replace("Z", "+00:00")
            task.event_start = datetime.fromisoformat(s)
        except Exception:
            task.event_start = None
    if isinstance(task.event_end, str) and task.event_end:
        try:
            s = task.event_end.replace("Z", "+00:00")
            task.event_end = datetime.fromisoformat(s)
        except Exception:
            task.event_end = None


@router.post("/", response_model=Task)
def create_task(task: Task, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    task.id = None
    task.owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    _coerce_task_types(task)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=Task)
def update_task(task_id: int, task_update: TaskUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    data = task_update.dict(exclude_unset=True)
    # coerce known fields
    if isinstance(data.get("deadline"), str):
        try:
            data["deadline"] = date.fromisoformat(data["deadline"]) if data["deadline"] else None
        except Exception:
            data["deadline"] = None
    for key in ("event_start", "event_end"):
        if isinstance(data.get(key), str):
            try:
                s = data[key].replace("Z", "+00:00") if data[key] else None
                data[key] = datetime.fromisoformat(s) if s else None
            except Exception:
                data[key] = None
    for k, v in data.items():
        setattr(task, k, v)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(task_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()
    return {"ok": True}


