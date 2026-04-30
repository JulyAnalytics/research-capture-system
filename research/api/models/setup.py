from typing import Optional
from pydantic import BaseModel


class SetupCreate(BaseModel):
    instrument: str
    setup_type: str
    note: str
    date: str


class SetupStatusTransition(BaseModel):
    status: str
    passed_reason: Optional[str] = None
    passed_reason_type: Optional[str] = None
