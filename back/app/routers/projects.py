from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy import delete as sa_delete
from typing import List

from ..db import get_session
from ..deps import get_current_user
from ..models import Project, Task


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=List[Project])
def list_projects(session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    statement = select(Project).where((Project.owner_id == owner_id) | (Project.owner_id.is_(None)))
    return session.exec(statement).all()


@router.post("/", response_model=Project)
def create_project(project: Project, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    project.id = None
    project.owner_id = int(current_user.get("id")) if current_user.get("id") is not None else None
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # Delete all tasks linked to this project, then delete the project itself
    session.exec(sa_delete(Task).where(Task.project_id == project_id))
    session.delete(project)
    session.commit()
    return {"ok": True}


