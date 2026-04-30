from typing import Optional
from pydantic import BaseModel


class ThesisCreate(BaseModel):
    instrument: str
    narrative: str
    win_condition: str


class ThesisUpdate(BaseModel):
    narrative: Optional[str] = None
    win_condition: Optional[str] = None
    worst_case_dollar: Optional[float] = None


class ThesisStatusTransition(BaseModel):
    status: str
    linked_trade_id: Optional[str] = None


class MacroKillConditionCreate(BaseModel):
    condition: str
    linked_canvas_id: Optional[str] = None


class TechnicalKillConditionCreate(BaseModel):
    condition: str
    linked_setup_id: Optional[str] = None


class KillConditionFire(BaseModel):
    pass


class DecisionPointCreate(BaseModel):
    trigger: str
    decision: str
    instrument: str
    size_pct: str


class DecisionPointFire(BaseModel):
    deviation_note: Optional[str] = None


class ThesisVersionHistoryCreate(BaseModel):
    diff_summary: str
