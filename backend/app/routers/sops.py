"""Teach mode endpoints. Phase 2: list/get only. Phase 3 adds POST /teach."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import SOP, Step

router = APIRouter()


@router.get("")
def list_sops(session: Session = Depends(get_session)) -> list[SOP]:
    return list(session.exec(select(SOP).order_by(SOP.created_at.desc())))


@router.get("/{sop_id}")
def get_sop(sop_id: int, session: Session = Depends(get_session)) -> dict:
    sop = session.get(SOP, sop_id)
    if not sop:
        raise HTTPException(404, "SOP not found")
    steps = session.exec(select(Step).where(Step.sop_id == sop_id).order_by(Step.idx)).all()
    return {"sop": sop, "steps": steps}
