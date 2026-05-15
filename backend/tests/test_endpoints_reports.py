from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.infrastructure.database.models.transaction import TransactionType
from app.services.transaction_service import TransactionService

NOW = datetime.now(timezone.utc)


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def transactions(db: AsyncSession, test_user):
    for type, amount, category, description in [
        (TransactionType.INCOME, "5000.00", "Renda", "Salário"),
        (TransactionType.EXPENSE, "800.00", "Alimentação", "Mercado"),
        (TransactionType.EXPENSE, "450.00", "Transporte", "Uber"),
    ]:
        await TransactionService.create(
            user_id=test_user.id,
            type=type,
            amount=Decimal(amount),
            description=description,
            category=category,
            date=NOW,
            db=db,
        )


async def test_balance_endpoint(client: AsyncClient, auth_headers, transactions):
    response = await client.get("/api/v1/reports/balance", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert float(data["total_income"]) == 5000.0
    assert float(data["total_expense"]) == 1250.0
    assert float(data["balance"]) == 3750.0
    assert "last_updated" in data


async def test_monthly_report_endpoint(client: AsyncClient, auth_headers, transactions):
    response = await client.get(
        f"/api/v1/reports/monthly?year={NOW.year}&month={NOW.month}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == f"{NOW.year}-{NOW.month:02d}"
    assert float(data["total_income"]) == 5000.0
    assert float(data["total_expense"]) == 1250.0
    assert isinstance(data["by_category"], list)
    assert len(data["by_category"]) == 2
    # Alimentação is the biggest expense
    assert data["by_category"][0]["category"] == "Alimentação"


async def test_monthly_report_defaults_to_current_month(
    client: AsyncClient, auth_headers, transactions
):
    response = await client.get("/api/v1/reports/monthly", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == f"{NOW.year}-{NOW.month:02d}"


async def test_by_category_endpoint(client: AsyncClient, auth_headers, transactions):
    response = await client.get("/api/v1/reports/by-category", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    assert "category" in data[0]
    assert "total" in data[0]
    assert "count" in data[0]
    assert "percentage" in data[0]
    # Should be sorted by total descending
    totals = [float(item["total"]) for item in data]
    assert totals == sorted(totals, reverse=True)


async def test_summary_endpoint(client: AsyncClient, auth_headers, transactions):
    response = await client.get("/api/v1/reports/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["recent_transactions"], list)
    assert len(data["recent_transactions"]) <= 5
    assert float(data["total_income"]) == 5000.0
    assert float(data["balance"]) == 3750.0
    assert "daily_average_expense" in data
    assert "largest_expense_this_month" in data
    assert "largest_income_this_month" in data


async def test_export_csv_endpoint(client: AsyncClient, auth_headers, transactions):
    response = await client.get("/api/v1/reports/export/csv", headers=auth_headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    lines = [ln for ln in response.text.strip().split("\n") if ln]
    assert lines[0] == "data,tipo,valor,categoria,descricao"
    assert len(lines) == 4  # header + 3 transactions


async def test_ai_insights_endpoint(client: AsyncClient, auth_headers, transactions):
    with patch("app.api.v1.endpoints.reports.AIService") as MockAI:
        instance = MockAI.return_value
        instance.generate_monthly_report = AsyncMock(
            return_value={
                "insight": "Seus gastos estão controlados.",
                "summary": "Saldo positivo.",
                "tips": ["Economize mais.", "Invista 10%."],
            }
        )
        response = await client.get("/api/v1/reports/ai-insights", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["insight"] == "Seus gastos estão controlados."
    assert data["summary"] == "Saldo positivo."
    assert isinstance(data["tips"], list)
    assert len(data["tips"]) == 2


async def test_reports_require_auth(client: AsyncClient):
    endpoints = [
        "/api/v1/reports/balance",
        "/api/v1/reports/monthly",
        "/api/v1/reports/by-category",
        "/api/v1/reports/summary",
        "/api/v1/reports/export/csv",
        "/api/v1/reports/ai-insights",
    ]
    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert (
            response.status_code == 403
        ), f"Expected 403 for {endpoint}, got {response.status_code}"
