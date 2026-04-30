from typing import Optional
from pydantic import BaseModel


class ObservationCreate(BaseModel):
    date: str
    instrument: str
    timeframe: str
    type: str
    observation: str
    linked_thesis_id: Optional[str] = None
