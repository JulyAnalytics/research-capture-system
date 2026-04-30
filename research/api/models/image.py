from typing import Optional
from pydantic import BaseModel


class ImageUploadResponse(BaseModel):
    id: str
    filename: str
    filepath: str
    caption: Optional[str] = None
