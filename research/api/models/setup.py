from pydantic import BaseModel


class SetupCreate(BaseModel):
    """
    Create a new setup (append-only after creation).

    Args:
        name:       Free-text label for the setup.
        instrument: Ticker symbol.
        type:       'technical', 'vol', or 'flow'
        timeframe:  Timeframe string (e.g. '4H', 'daily', 'weekly')
        setup_note: Prose description of the setup structure.
        date:       ISO date string (YYYY-MM-DD).
    """
    name: str
    instrument: str
    type: str
    timeframe: str
    setup_note: str
    date: str
