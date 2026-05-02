from typing import Literal, Optional
from pydantic import BaseModel, model_validator


class InsightCreate(BaseModel):
    """
    Create a new insight.

    Args:
        name:               Optional free-text label. Defaults to '' if absent.
        note:               Required prose capture — the insight itself.
        linked_entity_type: Optional. One of canvas|thesis|observation|setup|trade|review.
                            Must be provided together with linked_entity_id.
        linked_entity_id:   Optional. ULID of the linked entity. Must be provided
                            together with linked_entity_type.
        context_tag:        Optional freeform tag (e.g. 'pre-trade', 'macro').
                            Not validated against an enum — vocabulary is open.
    """
    name: str = ''
    note: str
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[str] = None
    context_tag: Optional[str] = None

    @model_validator(mode='after')
    def link_fields_paired(self) -> 'InsightCreate':
        """
        linked_entity_type and linked_entity_id must both be present or both absent.
        Raises ValueError (→ 422) if one is provided without the other.
        """
        has_type = self.linked_entity_type is not None
        has_id = self.linked_entity_id is not None
        if has_type != has_id:
            raise ValueError(
                'linked_entity_type and linked_entity_id must both be '
                'provided or both omitted'
            )
        return self
