from typing import Optional
from pydantic import BaseModel


class ActionCreate(BaseModel):
    action: str
    due_date: str
    instrument: Optional[str] = None
    linked_thesis_id: Optional[str] = None
    linked_setup_id: Optional[str] = None


class ActionCancel(BaseModel):
    cancellation_note: str
