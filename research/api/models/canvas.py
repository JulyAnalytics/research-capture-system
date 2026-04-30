from pydantic import BaseModel


class CanvasCreate(BaseModel):
    name: str
    narrative: str
    last_reviewed: str


class CanvasUpdate(BaseModel):
    narrative: str
    diff_summary: str


class CrossCurrentPayload(BaseModel):
    target_canvas_id: str
    relationship_description: str


class InvalidationConditionCreate(BaseModel):
    condition: str
    type: str  # 'necessary' or 'sufficient'
    probability: str  # 'low', 'medium', or 'high'
    lead_time_days: int
    last_assessed: str


class InvalidationConditionPatch(BaseModel):
    last_assessed: str
