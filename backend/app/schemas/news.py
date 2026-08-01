from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class NewsItem(BaseModel):
    id: int
    currency: str
    title: str
    impact: str
    time: datetime
    forecast: Optional[str] = None
    previous: Optional[str] = None
    actual: Optional[str] = None
    status: str

class NewsListResponse(BaseModel):
    events: List[NewsItem]
    lastUpdated: datetime
