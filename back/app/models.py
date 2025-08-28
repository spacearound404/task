from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: Optional[int] = Field(index=True, default=None)
    name: str
    color: str = "#BBF7D0"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    tasks: list["Task"] = Relationship(back_populates="project")


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: Optional[int] = Field(index=True, default=None)
    title: str
    description: str = ""
    deadline: Optional[date] = Field(default=None, index=True)
    duration_hours: float = 1.0
    priority: str = "medium"  # low|medium|high
    importance: str = "medium"  # low|medium|high
    kind: str = "task"  # task|event
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    project: Optional[Project] = Relationship(back_populates="tasks")


class TaskUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[date] = None
    duration_hours: Optional[float] = None
    priority: Optional[str] = None  # low|medium|high
    importance: Optional[str] = None  # low|medium|high
    kind: Optional[str] = None  # task|event
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    project_id: Optional[int] = None


class UserSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    # capacity per weekday 0..6 (Mon..Sun)
    hours_mon: int = 9
    hours_tue: int = 9
    hours_wed: int = 9
    hours_thu: int = 9
    hours_fri: int = 9
    hours_sat: int = 9
    hours_sun: int = 9
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AiSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-5"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    role: str  # system|user|assistant
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


