import json
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from app.core.exceptions import AIServiceError


@pytest.fixture
def mock_anthropic_client():
    with patch("app.infrastructure.ai.claude_provider.anthropic.AsyncAnthropic") as MockClass:
        mock_client = MagicMock()
        MockClass.return_value = mock_client
        yield mock_client


def _make_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=10, output_tokens=20)
    return resp


@pytest.mark.asyncio
async def test_classify_transaction_expense(mock_anthropic_client):
    from app.infrastructure.ai.claude_provider import ClaudeProvider

    payload = {
        "type": "EXPENSE",
        "category": "Alimentação",
        "amount": 50.0,
        "confidence": 0.97,
        "explanation": "Compra em mercado",
    }
    mock_anthropic_client.messages.create = AsyncMock(
        return_value=_make_response(json.dumps(payload))
    )

    provider = ClaudeProvider()
    result = await provider.classify_transaction("Gastei R$50 no mercado")

    assert result["type"] == "EXPENSE"
    assert result["category"] == "Alimentação"
    assert result["amount"] == 50.0
    assert result["confidence"] == 0.97


@pytest.mark.asyncio
async def test_classify_transaction_income(mock_anthropic_client):
    from app.infrastructure.ai.claude_provider import ClaudeProvider

    payload = {
        "type": "INCOME",
        "category": "Renda",
        "amount": 5000.0,
        "confidence": 0.99,
        "explanation": "Salário recebido",
    }
    mock_anthropic_client.messages.create = AsyncMock(
        return_value=_make_response(json.dumps(payload))
    )

    provider = ClaudeProvider()
    result = await provider.classify_transaction("Recebi 5000 de salário")

    assert result["type"] == "INCOME"
    assert result["amount"] == 5000.0


@pytest.mark.asyncio
async def test_generate_insight(mock_anthropic_client):
    from app.infrastructure.ai.claude_provider import ClaudeProvider

    payload = {
        "insight": "Você gastou 40% em alimentação.",
        "summary": "Mês equilibrado.",
        "tips": ["Reduza gastos em lazer", "Guarde 10% da renda"],
    }
    mock_anthropic_client.messages.create = AsyncMock(
        return_value=_make_response(json.dumps(payload))
    )

    provider = ClaudeProvider()
    result = await provider.generate_financial_insight([{"total": 1000}])

    assert result["insight"] == "Você gastou 40% em alimentação."
    assert len(result["tips"]) == 2


@pytest.mark.asyncio
async def test_handle_rate_limit_error(mock_anthropic_client):
    from app.infrastructure.ai.claude_provider import ClaudeProvider

    mock_anthropic_client.messages.create = AsyncMock(
        side_effect=anthropic.RateLimitError(
            message="rate limit", response=MagicMock(status_code=429), body={}
        )
    )

    provider = ClaudeProvider()
    with pytest.raises(AIServiceError, match="Rate limit"):
        await provider.classify_transaction("teste")


@pytest.mark.asyncio
async def test_handle_auth_error(mock_anthropic_client):
    from app.infrastructure.ai.claude_provider import ClaudeProvider

    mock_anthropic_client.messages.create = AsyncMock(
        side_effect=anthropic.AuthenticationError(
            message="invalid key", response=MagicMock(status_code=401), body={}
        )
    )

    provider = ClaudeProvider()
    with pytest.raises(AIServiceError, match="inválida"):
        await provider.classify_transaction("teste")


@pytest.mark.asyncio
async def test_classify_invalid_json_raises(mock_anthropic_client):
    from app.infrastructure.ai.claude_provider import ClaudeProvider

    mock_anthropic_client.messages.create = AsyncMock(
        return_value=_make_response("não é json")
    )

    provider = ClaudeProvider()
    with pytest.raises(AIServiceError):
        await provider.classify_transaction("teste")


@pytest.mark.asyncio
async def test_answer_financial_question(mock_anthropic_client):
    from app.infrastructure.ai.claude_provider import ClaudeProvider

    mock_anthropic_client.messages.create = AsyncMock(
        return_value=_make_response("Você gastou R$ 800 este mês.")
    )

    provider = ClaudeProvider()
    result = await provider.answer_financial_question(
        "quanto gastei?", {"saldo_mes": -800}
    )

    assert "800" in result
