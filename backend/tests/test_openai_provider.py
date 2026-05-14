import json
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from app.core.exceptions import AIServiceError


@pytest.fixture
def mock_openai_client():
    with patch("app.infrastructure.ai.openai_provider.openai.AsyncOpenAI") as MockClass:
        mock_client = MagicMock()
        MockClass.return_value = mock_client
        yield mock_client


def _make_response(text: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
    return resp


@pytest.mark.asyncio
async def test_classify_transaction_expense(mock_openai_client):
    from app.infrastructure.ai.openai_provider import OpenAIProvider

    payload = {
        "type": "EXPENSE",
        "category": "Alimentação",
        "amount": 50.0,
        "confidence": 0.97,
        "explanation": "Compra em mercado",
    }
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_make_response(json.dumps(payload))
    )

    provider = OpenAIProvider()
    result = await provider.classify_transaction("Gastei R$50 no mercado")

    assert result["type"] == "EXPENSE"
    assert result["category"] == "Alimentação"
    assert result["amount"] == 50.0


@pytest.mark.asyncio
async def test_classify_transaction_income(mock_openai_client):
    from app.infrastructure.ai.openai_provider import OpenAIProvider

    payload = {
        "type": "INCOME",
        "category": "Renda",
        "amount": 5000.0,
        "confidence": 0.99,
        "explanation": "Salário recebido",
    }
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_make_response(json.dumps(payload))
    )

    provider = OpenAIProvider()
    result = await provider.classify_transaction("Recebi 5000 de salário")

    assert result["type"] == "INCOME"
    assert result["amount"] == 5000.0


@pytest.mark.asyncio
async def test_generate_insight(mock_openai_client):
    from app.infrastructure.ai.openai_provider import OpenAIProvider

    payload = {
        "insight": "Você gastou 40% em alimentação.",
        "summary": "Mês equilibrado.",
        "tips": ["Reduza gastos em lazer", "Guarde 10% da renda"],
    }
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_make_response(json.dumps(payload))
    )

    provider = OpenAIProvider()
    result = await provider.generate_financial_insight([{"total": 1000}])

    assert result["insight"] == "Você gastou 40% em alimentação."
    assert len(result["tips"]) == 2


@pytest.mark.asyncio
async def test_handle_rate_limit_error(mock_openai_client):
    from app.infrastructure.ai.openai_provider import OpenAIProvider

    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=openai.RateLimitError(
            message="rate limit", response=MagicMock(status_code=429), body={}
        )
    )

    provider = OpenAIProvider()
    with pytest.raises(AIServiceError, match="Rate limit"):
        await provider.classify_transaction("teste")


@pytest.mark.asyncio
async def test_handle_auth_error(mock_openai_client):
    from app.infrastructure.ai.openai_provider import OpenAIProvider

    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=openai.AuthenticationError(
            message="invalid key", response=MagicMock(status_code=401), body={}
        )
    )

    provider = OpenAIProvider()
    with pytest.raises(AIServiceError, match="inválida"):
        await provider.classify_transaction("teste")


@pytest.mark.asyncio
async def test_classify_invalid_json_raises(mock_openai_client):
    from app.infrastructure.ai.openai_provider import OpenAIProvider

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_make_response("não é json")
    )

    provider = OpenAIProvider()
    with pytest.raises(AIServiceError):
        await provider.classify_transaction("teste")


@pytest.mark.asyncio
async def test_answer_financial_question(mock_openai_client):
    from app.infrastructure.ai.openai_provider import OpenAIProvider

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_make_response("Você gastou R$ 800 este mês.")
    )

    provider = OpenAIProvider()
    result = await provider.answer_financial_question(
        "quanto gastei?", {"saldo_mes": -800}
    )

    assert "800" in result


@pytest.mark.asyncio
async def test_ai_service_uses_openai_when_configured(mock_openai_client):
    """Verifica que AIService instancia OpenAIProvider quando AI_PROVIDER=openai."""
    from unittest.mock import patch as mock_patch

    with mock_patch("app.core.config.settings.AI_PROVIDER", "openai"):
        from app.services.ai_service import _build_provider
        from app.infrastructure.ai.openai_provider import OpenAIProvider
        provider = _build_provider()
        assert isinstance(provider, OpenAIProvider)


@pytest.mark.asyncio
async def test_ai_service_uses_claude_when_configured():
    """Verifica que AIService instancia ClaudeProvider quando AI_PROVIDER=claude."""
    from unittest.mock import patch as mock_patch

    with mock_patch("app.core.config.settings.AI_PROVIDER", "claude"):
        from app.services.ai_service import _build_provider
        from app.infrastructure.ai.claude_provider import ClaudeProvider
        provider = _build_provider()
        assert isinstance(provider, ClaudeProvider)
