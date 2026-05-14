from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.report import (
    AIInsightsResponse,
    BalanceResponse,
    CategoryReportItem,
    MonthlyReportResponse,
    SummaryResponse,
)
from app.services.ai_service import AIService
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_balance(current_user.id, db)


@router.get("/monthly", response_model=MonthlyReportResponse)
async def get_monthly_report(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    return await ReportService.get_monthly_report(
        current_user.id,
        year if year is not None else now.year,
        month if month is not None else now.month,
        db,
    )


@router.get("/by-category", response_model=list[CategoryReportItem])
async def get_by_category(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_by_category(current_user.id, db, date_from, date_to)


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_summary(current_user.id, db)


@router.get("/export/csv")
async def export_csv(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    csv_content = await ReportService.export_csv(current_user.id, db, date_from, date_to)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/ai-insights", response_model=AIInsightsResponse)
async def get_ai_insights(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ai_service = AIService()
    result = await ReportService.get_ai_insights(current_user.id, db, ai_service)
    return result
