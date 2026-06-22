"""
Portfolio Router — endpoints to retrieve company portfolios and manually refresh aggregations.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.company_portfolio import CompanyPortfolio
from app.services.portfolio_engine import PortfolioEngine
from app.schemas.portfolio import CompanyPortfolioResponse
from app.utils.exceptions import NotFoundException, ForbiddenException, BadRequestException

router = APIRouter(prefix="/api/v1/portfolio", tags=["Company Portfolios"])


@router.get("/companies", response_model=List[CompanyPortfolioResponse])
def get_companies_portfolios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve portfolio summaries for all companies."""
    # Regular users can only see portfolios if they are associated with a company
    # Admins can see all portfolios.
    stmt = select(CompanyPortfolio)
    if not current_user.is_admin and current_user.company_name:
        stmt = stmt.where(CompanyPortfolio.company_name == current_user.company_name)
    elif not current_user.is_admin:
        # Standard user without company can only see "Independent" or nothing
        stmt = stmt.where(CompanyPortfolio.company_name == "Independent")
        
    stmt = stmt.order_by(desc(CompanyPortfolio.last_generated_at))
    return list(db.execute(stmt).scalars().all())


@router.get("/company/{name}", response_model=CompanyPortfolioResponse)
def get_company_portfolio(
    name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve detailed portfolio for a single company."""
    if not current_user.is_admin and current_user.company_name != name:
        raise ForbiddenException(detail="You do not have access to this company's portfolio")

    portfolio = db.query(CompanyPortfolio).filter(CompanyPortfolio.company_name == name).first()
    if not portfolio:
        raise NotFoundException(detail="Company portfolio report not found.")
    return portfolio


@router.post("/generate")
def generate_all_portfolios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually trigger portfolio calculations and reports generation for all companies."""
    if not current_user.is_admin:
        raise ForbiddenException(detail="Admin privilege required for this action")

    engine = PortfolioEngine(db)
    portfolios = engine.generate_all_portfolios()
    return {"message": "Successfully refreshed portfolios.", "companies_count": len(portfolios)}
