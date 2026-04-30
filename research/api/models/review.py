from typing import Optional
from pydantic import BaseModel


class ReviewCreate(BaseModel):
    trade_id: str
    closed_at: str
    entry_fill: str
    exit_fill: str
    thesis_at_entry: str
    exit_rules_as_written: str
    what_i_actually_did: str
    emotional_state: str
    rules_followed: str


class Zone3Clear(BaseModel):
    pass


class Phase2Payload(BaseModel):
    mistake_type: str
    analysis: str
    single_update: str
    what_not_changing: str
