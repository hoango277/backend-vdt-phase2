from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.schemas import UserContext


class NetworkEvent(BaseModel):
    user: Optional[UserContext] = None
    request: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None
    sequence : Optional[int] = None
    timing: Optional[Dict[str, Any]] = None
    timestamp: Optional[int] = None
    requestId: Optional[str] = None



    class Config:
        extra = "allow"