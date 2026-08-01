from pydantic import BaseModel
from typing import List

class MarketItem(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    changePercent: float
    isPositive: bool
    marketStatus: str

class MarketListResponse(BaseModel):
    markets: List[MarketItem]
    lastUpdated: str
