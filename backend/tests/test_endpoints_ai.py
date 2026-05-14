from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.transaction import TransactionType
from app.main import app
from app.services.ai_service import AIService, TransactionSuggestion
from app.services.auth_service import AuthService


@pytest_asyncio.fixture
async def auth_headers(db: AsyncSession):
    user = await AuthService.register(
        email="ai_test@test.com",
        password="TestPass123!",
        full_name="AI Test User",
        db=db,
    )
    from app.core.security import create_access_token
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}, user


@pytest.mark.asyncio
async def test_analyze_endpoint_success(client, auth_headers):
    headers, user = auth_headers

    mock_suggestion = TransactionSuggestion(
        type=TransactionType.INCOME,
        category="Freelance",
        amount=Decimal("5000"),
        confidence=0.98,
        explanation="Recebimento de freelance",
    )

    with patch.object(AIService, "analyze_transaction", new=AsyncMock(return_value=mock_suggestion)):
        resp = await client.post(
            "/api/v1/ai/analyze",
            json={"text": "recebi 5000 freelance semana passada"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "INCOME"
    assert data["category"] == "Freelance"
    assert data["amount"] == 5000.0
    assert data["confidence"] == 0.98


@pytest.mark.asyncio
async def test_analyze_endpoint_no_auth(client):
    resp = await client.post(
        "/api/v1/ai/analyze",
        json={"text": "recebi 5000 freelance"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_insight_endpoint_success(client, auth_headers):
    headers, user = auth_headers

    mock_result = {
        "insight": "Você gastou 40% em alimentação este mês.",
        "summary": "Mês com saldo positivo.",
        "tips": ["Reduza gastos em lazer", "Poupe 20% da renda"],
    }

    with patch.object(AIService, "generate_monthly_report", new=AsyncMock(return_value=mock_result)):
        resp = await client.get(
            f"/api/v1/ai/insight/{user.id}",
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "insight" in data
    assert isinstance(data["tips"], list)


@pytest.mark.asyncio
async def test_insight_endpoint_wrong_user(client, auth_headers):
    import uuid
    headers, user = auth_headers

    other_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/ai/insight/{other_id}",
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_question_endpoint_success(client, auth_headers):
    headers, user = auth_headers

    with patch.object(
        AIService, "answer_question",
        new=AsyncMock(return_value="Você gastou R$ 2.340 este mês.")
    ):
        resp = await client.post(
            "/api/v1/ai/question",
            json={"question": "quanto gastei esse mês?"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert data["context_used"] is True


@pytest.mark.asyncio
async def test_question_endpoint_no_auth(client):
    resp = await client.post(
        "/api/v1/ai/question",
        json={"question": "quanto gastei?"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analyze_endpoint_empty_text(client, auth_headers):
    headers, _ = auth_headers
    resp = await client.post(
        "/api/v1/ai/analyze",
        json={"text": ""},
        headers=headers,
    )
    assert resp.status_code == 422
