from typing import Literal, Optional
from pydantic import BaseModel, model_validator


class ObservationCreate(BaseModel):
    """
    Create a new observation (watching state).

    Args:
        name:       Free-text label for the observation.
        instrument: Ticker symbol being observed.
        note:       Prose description of what was observed.
        date:       ISO date string (YYYY-MM-DD).

    Returns on POST /observation: {id: str}
    """
    name: str
    instrument: str
    note: str
    date: str


class ObservationStatusTransition(BaseModel):
    """
    Transition observation status: watching → taken or passed.

    For 'passed', passed_reason and passed_reason_type are required —
    validated here as a 422 before the request reaches the DB trigger.
    Terminal state enforcement (taken/passed → any) is handled by the
    observation_state_machine trigger, which returns a raw IntegrityError
    message converted to a 400 by the route. This is intentional and
    consistent with all other state machine routes in this codebase.

    Args:
        status:             'taken' or 'passed' — Literal, validated by Pydantic
        passed_reason:      Required when status = 'passed'
        passed_reason_type: 'psychological' or 'analytical' — required when passed
    """
    status: Literal['taken', 'passed']
    passed_reason: Optional[str] = None
    passed_reason_type: Optional[Literal['psychological', 'analytical']] = None

    @model_validator(mode='after')
    def passed_fields_required(self) -> 'ObservationStatusTransition':
        """
        When status is 'passed', both passed_reason and passed_reason_type
        must be present. Raises ValueError (→ 422) before the request hits
        the DB trigger, producing a cleaner error message than the raw
        IntegrityError.
        """
        if self.status == 'passed':
            if not self.passed_reason or not self.passed_reason.strip():
                raise ValueError('passed_reason is required when status is passed')
            if self.passed_reason_type is None:
                raise ValueError('passed_reason_type is required when status is passed')
        return self
