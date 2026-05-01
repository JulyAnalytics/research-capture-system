from typing import Literal, Optional
from pydantic import BaseModel


class TradeCreate(BaseModel):
    """
    Create a trade. Default status is 'idea'.

    If thesis_id, entry_rules_stated, and exit_rules_stated are all provided,
    the route will fast-path the trade to 'active' status. Otherwise the trade
    is created as 'idea' and activated separately via PATCH /trade/{id}/activate.
    """
    name: str
    instrument_type: Literal['equity', 'option', 'future', 'fx', 'other']
    instrument: Optional[str] = None
    idea_note: Optional[str] = None
    thesis_id: Optional[str] = None
    entry_rules_stated: Optional[str] = None
    exit_rules_stated: Optional[str] = None


class TradeActivate(BaseModel):
    """
    Activate an idea trade (idea → active transition).

    thesis_snapshot is populated server-side from thesis.narrative — do not
    pass it as a client field.

    Thesis substitution policy: if the trade already has a thesis_id set,
    providing a different thesis_id requires force_thesis_change=True.
    """
    thesis_id: str
    entry_rules_stated: str
    exit_rules_stated: str
    force_thesis_change: bool = False


class TradeClose(BaseModel):
    """Close an active trade. review_id is optional — can be set separately."""
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
    direction: Literal['long', 'short']
    type: Literal['call', 'put']
    strike: float
    expiry: str
    contracts: int
    entry_premium: float
    date_opened: str


class OptionLegUpdate(BaseModel):
    exit_premium: Optional[float] = None
    date_closed: Optional[str] = None
