from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AIServiceError
from app.infrastructure.database.models.transaction import TransactionType
from app.services.ai_service import AIService, TransactionSuggestion


def _mock_provider(classify_return=None, insight_return=None, question_return=None, enhance_return=None):
    provider = MagicMock()
    if classify_return is not None:
        provider.classify_transaction = AsyncMock(return_value=classify_return)
    if insight_return is not None:
        provider.generate_financial_insight = AsyncMock(return_value=insight_return)
    if question_return is not None:
        provider.answer_financial_question = AsyncMock(return_value=question_return)
    if enhance_return is not None:
        provider.improve_whatsapp_response = AsyncMock(return_value=enhance_return)
    return provider


@pytest.mark.asyncio
async def test_analyze_transaction_expense():
    svc = AIService.__new__(AIService)
    svc._provider = _mock_provider(classify_return={
        "type": "EXPENSE",
        "category": "Alimentação",
        "amount": 50.0,
        "confidence": 0.97,
        "explanation": "Compra de mercado",
    })

    result = await svc.analyze_transaction("Gastei R$50 no mercado")

    assert result.type == TransactionType.EXPENSE
    assert result.category == "Alimentação"
    assert result.amount == Decimal("50.0")
    assert result.confidence == 0.97


@pytest.mark.asyncio
async def test_analyze_transaction_income():
    svc = AIService.__new__(AIService)
    svc._provider = _mock_provider(classify_return={
        "type": "INCOME",
        "category": "Renda",
        "amount": 5000.0,
        "confidence": 0.99,
        "explanation": "Salário",
    })

    result = await svc.analyze_transaction("Recebi salário de 5000")

    assert result.type == TransactionType.INCOME
    assert result.amount == Decimal("5000.0")


@pytest.mark.asyncio
async def test_analyze_transaction_no_amount():
    svc = AIService.__new__(AIService)
    svc._provider = _mock_provider(classify_return={
        "type": "EXPENSE",
        "category": "Outros",
        "amount": None,
        "confidence": 0.6,
        "explanation": "Valor não identificado",
    })

    result = await svc.analyze_transaction("gastei alguma coisa")

    assert result.amount is None
    assert result.confidence == 0.6


@pytest.mark.asyncio
async def test_generate_monthly_report(db: AsyncSession, test_user):
    from datetime import datetime, timezone
    from decimal import Decimal
    from app.services.transaction_service import TransactionService
    from app.infrastructure.database.models.transaction import TransactionType

    await TransactionService.create(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("200"),
        description="Mercado",
        category="Alimentação",
        date=datetime.now(timezone.utc),
        db=db,
    )

    svc = AIService.__new__(AIService)
    expected = {
        "insight": "Você gastou bem esse mês.",
        "summary": "Saldo positivo.",
        "tips": ["Dica 1"],
    }
    svc._provider = _mock_provider(insight_return=expected)

    result = await svc.generate_monthly_report(str(test_user.id), db)

    assert result["insight"] == "Você gastou bem esse mês."
    assert "tips" in result


@pytest.mark.asyncio
async def test_generate_monthly_report_no_transactions(db: AsyncSession, test_user):
    svc = AIService.__new__(AIService)
    svc._provider = _mock_provider()

    result = await svc.generate_monthly_report(str(test_user.id), db)

    # No transactions → no AI call, returns default message
    assert "Nenhuma transação" in result["insight"]
    svc._provider.generate_financial_insight.assert_not_called() if hasattr(
        svc._provider, "generate_financial_insight"
    ) else None


@pytest.mark.asyncio
async def test_answer_financial_question(db: AsyncSession, test_user):
    svc = AIService.__new__(AIService)
    svc._provider = _mock_provider(question_return="Você gastou R$ 300 este mês.")

    result = await svc.answer_question("quanto gastei?", str(test_user.id), db)

    assert "300" in result


@pytest.mark.asyncio
async def test_ai_fallback_on_error():
    svc = AIService.__new__(AIService)
    provider = MagicMock()
    provider.classify_transaction = AsyncMock(side_effect=AIServiceError("falha"))
    svc._provider = provider

    with pytest.raises(AIServiceError):
        await svc.analyze_transaction("teste")


@pytest.mark.asyncio
async def test_enhance_whatsapp_returns_original_on_error(db: AsyncSession, test_user):
    svc = AIService.__new__(AIService)
    provider = MagicMock()
    provider.improve_whatsapp_response = AsyncMock(side_effect=AIServiceError("falha"))
    svc._provider = provider

    original = "✓ Gasto registrado!"
    result = await svc.enhance_whatsapp_response(original, str(test_user.id), db)

    assert result == original
