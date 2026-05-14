from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BalanceResponse(BaseModel):
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal
    last_updated: datetime


class CategoryReportItem(BaseModel):
    category: str
    total: Decimal
    count: int
    percentage: float


class MonthlyReportResponse(BaseModel):
    period: str
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal
    by_category: list[CategoryReportItem]


class SummaryTransactionItem(BaseModel):
    id: str
    type: str
    amount: Decimal
    category: str
    description: str
    date: str


class SummaryResponse(BaseModel):
    recent_transactions: list[SummaryTransactionItem]
    largest_expense_this_month: Decimal | None
    largest_income_this_month: Decimal | None
    daily_average_expense: Decimal
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal


class ExportRequest(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None


class AIInsightsResponse(BaseModel):
    insight: str
    summary: str
    tips: list[str]
