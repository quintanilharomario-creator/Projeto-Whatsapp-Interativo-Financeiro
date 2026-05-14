import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from time import monotonic

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AIServiceError, RateLimitError
from app.core.logging import get_logger
from app.infrastructure.ai.claude_provider import ClaudeProvider
from app.infrastructure.database.models.transaction import TransactionType
from app.services.transaction_service import TransactionService

logger = get_logger(__name__)

_MAX_CALLS_PER_MINUTE = 10
_user_call_times: dict[str, deque] = {}


@dataclass
class TransactionSuggestion:
    type: TransactionType
    category: str
    amount: Decimal | None
    confidence: float
    explanation: str


def _check_rate_limit(user_id: str) -> None:
    now = monotonic()
    if user_id not in _user_call_times:
        _user_call_times[user_id] = deque()
    dq = _user_call_times[user_id]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= _MAX_CALLS_PER_MINUTE:
        raise RateLimitError()
    dq.append(now)


class AIService:
    def __init__(self) -> None:
        self._provider = ClaudeProvider()

    async def analyze_transaction(
        self,
        text: str,
        user_id: str | None = None,
    ) -> TransactionSuggestion:
        if user_id:
            _check_rate_limit(user_id)
        try:
            result = await self._provider.classify_transaction(text)
            txn_type = (
                TransactionType.INCOME
                if str(result.get("type", "EXPENSE")).upper() == "INCOME"
                else TransactionType.EXPENSE
            )
            amount_raw = result.get("amount")
            amount: Decimal | None = None
            if amount_raw is not None:
                try:
                    v = Decimal(str(amount_raw))
                    amount = v if v > 0 else None
                except Exception:
                    pass
            return TransactionSuggestion(
                type=txn_type,
                category=result.get("category") or "Outros",
                amount=amount,
                confidence=float(result.get("confidence", 0.5)),
                explanation=result.get("explanation") or "",
            )
        except (AIServiceError, RateLimitError):
            raise
        except Exception as e:
            logger.error("ai_analyze_transaction_error", error=str(e))
            raise AIServiceError("Erro ao analisar transação com IA.")

    async def generate_monthly_report(
        self,
        user_id: str,
        db: AsyncSession,
    ) -> dict:
        _check_rate_limit(user_id)
        now = datetime.now(timezone.utc)
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        transactions = await TransactionService.list_by_user(
            user_id=uuid.UUID(user_id),
            db=db,
            date_from=date_from,
        )

        if not transactions:
            return {
                "insight": "Nenhuma transação registrada este mês.",
                "summary": "Sem movimentações.",
                "tips": ["Registre suas despesas para obter análises personalizadas."],
            }

        total_income = sum(float(t.amount) for t in transactions if t.type == TransactionType.INCOME)
        total_expense = sum(float(t.amount) for t in transactions if t.type == TransactionType.EXPENSE)

        context = {
            "mes": now.strftime("%B/%Y"),
            "total_receitas": total_income,
            "total_despesas": total_expense,
            "saldo": total_income - total_expense,
            "transacoes": [
                {
                    "type": t.type.value,
                    "amount": float(t.amount),
                    "category": t.category,
                    "date": t.date.date().isoformat(),
                }
                for t in transactions
            ],
        }

        return await self._provider.generate_financial_insight([context])

    async def answer_question(
        self,
        question: str,
        user_id: str,
        db: AsyncSession,
    ) -> str:
        _check_rate_limit(user_id)
        now = datetime.now(timezone.utc)
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        transactions = await TransactionService.list_by_user(
            user_id=uuid.UUID(user_id),
            db=db,
            date_from=date_from,
        )

        total_income = sum(float(t.amount) for t in transactions if t.type == TransactionType.INCOME)
        total_expense = sum(float(t.amount) for t in transactions if t.type == TransactionType.EXPENSE)

        context = {
            "saldo_mes": round(total_income - total_expense, 2),
            "total_receitas_mes": round(total_income, 2),
            "total_despesas_mes": round(total_expense, 2),
            "num_transacoes": len(transactions),
            "transacoes_recentes": [
                {
                    "type": t.type.value,
                    "amount": float(t.amount),
                    "category": t.category,
                    "date": t.date.date().isoformat(),
                }
                for t in transactions[:20]
            ],
        }

        return await self._provider.answer_financial_question(question, context)

    async def enhance_whatsapp_response(
        self,
        message: str,
        user_id: str,
        db: AsyncSession,
    ) -> str:
        try:
            _check_rate_limit(user_id)
            now = datetime.now(timezone.utc)
            date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            transactions = await TransactionService.list_by_user(
                user_id=uuid.UUID(user_id),
                db=db,
                date_from=date_from,
            )
            total_expense = sum(
                float(t.amount) for t in transactions if t.type == TransactionType.EXPENSE
            )
            context = {
                "gasto_total_mes": round(total_expense, 2),
                "num_transacoes_mes": len(transactions),
            }
            return await self._provider.improve_whatsapp_response(message, context)
        except Exception:
            logger.warning("enhance_whatsapp_fallback", user_id=user_id)
            return message
