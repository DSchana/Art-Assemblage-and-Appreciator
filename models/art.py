import uuid

from pydantic import BaseModel
from typing import Optional, List

class Assemblage(BaseModel):
    id: Optional[str] = str(uuid.uuid4())
    name: Optional[str] = None
    art: Optional[List[str]] = []

class Art(BaseModel):
    name: Optional[str] = None
    src: Optional[str]
    tags: Optional[List[str]] = []