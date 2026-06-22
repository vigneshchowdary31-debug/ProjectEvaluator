"""
Pydantic schemas for Company Portfolio reports.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CompanyPortfolioResponse(BaseModel):
    id: str
    company_name: str
    projects_count: int
    avg_completion: float
    avg_security: float
    avg_readiness: float
    projects_at_risk: int
    top_risks: Optional[List[Dict[str, Any]]]
    health_rating: str
    report_url: Optional[str]
    last_generated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
