from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

REQUIRED_FIELDS = [
    "CUSIP", "security_type", "issue_date", "maturity_date", "coupon_rate",
    "clean_bid", "clean_ask", "last_price", "quote_timestamp", "source", "data_status",
]

@dataclass(frozen=True)
class TreasurySecurity:
    CUSIP: str
    security_type: str
    issue_date: date
    maturity_date: date
    coupon_rate: float
    clean_bid: float
    clean_ask: float
    last_price: float
    quote_timestamp: datetime
    source: str
    data_status: str
    auction_date: Optional[date] = None
    auction_yield: Optional[float] = None
