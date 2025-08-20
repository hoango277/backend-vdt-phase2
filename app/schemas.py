from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List


class UserContext(BaseModel):
    username: Optional[str] = None
    sessionId: Optional[str] = None
    domain: Optional[str] = None
    pageUrl: Optional[str] = None



class HealthStatus(BaseModel):
    db_ok: bool
    es_ok: bool
    details: Dict[str, Any] = Field(default_factory=dict)
