from typing import Optional
from pydantic import BaseModel


class TradeCreate(BaseModel):
    thesis_id: str
    instrument_type: str
    entry_rules_stated: str
    exit_rules_stated: str


class TradeClose(BaseModel):
    review_id: Optional[str] = None


class TradeEntryCreate(BaseModel):
    date: str
    price: float
    size: float
    note: Optional[str] = None


class TradeExitCreate(BaseModel):
    date: str
    price: float
    size: float
    note: Optional[str] = None


class OptionsMetaCreate(BaseModel):
    strategy_type: str
    iv_at_entry: float
    iv_rank_at_entry: float
    max_loss_defined: int
    theta_decay_relevant: int
    delta_at_entry: Optional[float] = None
    gamma_at_entry: Optional[float] = None
    theta_daily_at_entry: Optional[float] = None
    vega_at_entry: Optional[float] = None
    delta_at_exit: Optional[float] = None
    gamma_at_exit: Optional[float] = None
    theta_daily_at_exit: Optional[float] = None
    vega_at_exit: Optional[float] = None
    iv_at_exit: Optional[float] = None
    max_loss_dollar: Optional[float] = None


class OptionLegCreate(BaseModel):
    direction: str
    type: str
    strike: float
    expiry: str
    contracts: int
    entry_premium: float
    date_opened: str


class OptionLegUpdate(BaseModel):
    exit_premium: Optional[float] = None
    date_closed: Optional[str] = None
