"""Database tables (SQLModel = SQLAlchemy + Pydantic in one class)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class SOP(SQLModel, table=True):
    """A procedure taught once by an expert (Teach mode)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = "Untitled SOP"
    video_path: str = ""
    transcript: str = ""
    status: str = "uploaded"  # uploaded -> transcribing -> building -> segmenting -> ready | failed
    error: str = ""
    created_at: datetime = Field(default_factory=now)


class Step(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sop_id: int = Field(foreign_key="sop.id", index=True)
    idx: int  # 1-based order within the SOP
    action: str
    parts: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tools: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    expected_end_state: str = ""
    critical: bool = False
    start_sec: float = 0.0
    end_sec: float = 0.0
    thumbnail_path: str = ""


class CheckRun(SQLModel, table=True):
    """One worker doing the SOP (Check mode)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    sop_id: int = Field(foreign_key="sop.id", index=True)
    worker_language: str = "en"  # en | kn | hi
    current_step: int = 1
    status: str = "active"  # active | done
    created_at: datetime = Field(default_factory=now)


class Event(SQLModel, table=True):
    """Every agent decision, stored with its evidence."""
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="checkrun.id", index=True)
    step_idx: int
    kind: str  # pass | flag | override
    deviation_type: str = ""  # skip | wrong_order | wrong_part | missing | unclear
    observed_step_id: Optional[int] = None
    reason: str = ""
    evidence: str = ""
    instruction: str = ""  # what the worker hears
    observation: str = ""  # blind observation text
    clip_path: str = ""
    latency_s: float = 0.0
    created_at: datetime = Field(default_factory=now)
