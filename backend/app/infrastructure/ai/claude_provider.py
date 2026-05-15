import json
from typing import Any

import anthropic

from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.infrastructure.ai.prompts.financial_prompt import (
    CLASSIFY_TRANSACTION_SYSTEM,
    FINANCIAL_INSIGHT_SYSTEM,
    FINANCIAL_QUESTION_SYSTEM,
    WHATSAPP_RESPONSE_SYSTEM,
)

logger = get_logger(__name__)

_TIMEOUT = 30.0


class ClaudeProvider:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=_TIMEOUT,
        )
        self._model = settings.ANTHROPIC_MODEL

    async def _call(
        self, system: str, user_message: str, max_tokens: int = 1024
    ) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            logger.info(
                "claude_api_call",
                model=self._model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return response.content[0].text
        except anthropic.RateLimitError as e:
            logger.warning("claude_rate_limit", error=str(e))
            raise AIServiceError(
                "Rate limit atingido. Tente novamente em alguns minutos."
            )
        except anthropic.AuthenticationError as e:
            logger.error("claude_auth_error", error=str(e))
            raise AIServiceError("Chave de API do Claude inválida.")
        except anthropic.APIError as e:
            logger.error(
                "claude_api_error",
                status_code=getattr(e, "status_code", None),
                error=str(e),
            )
            raise AIServiceError(f"Erro na API do Claude: {e}")

    async def classify_transaction(self, text: str) -> dict[str, Any]:
        raw = await self._call(
            CLASSIFY_TRANSACTION_SYSTEM,
            f'Classifique esta transação financeira: "{text}"',
            max_tokens=256,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("claude_json_parse_error", raw=raw[:200])
            raise AIServiceError(
                "Resposta inválida do Claude ao classificar transação."
            )

    async def generate_financial_insight(
        self, transactions: list[dict]
    ) -> dict[str, Any]:
        prompt = (
            f"Transações do mês:\n"
            f"{json.dumps(transactions, ensure_ascii=False, indent=2)}\n\n"
            f"Gere o relatório mensal."
        )
        raw = await self._call(FINANCIAL_INSIGHT_SYSTEM, prompt, max_tokens=1024)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"insight": raw, "summary": raw.split(".")[0] + ".", "tips": []}

    async def answer_financial_question(self, question: str, context: dict) -> str:
        prompt = (
            f"Contexto financeiro:\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"Pergunta: {question}"
        )
        return await self._call(FINANCIAL_QUESTION_SYSTEM, prompt, max_tokens=512)

    async def improve_whatsapp_response(self, raw_response: str, context: dict) -> str:
        prompt = (
            f"Contexto: {json.dumps(context, ensure_ascii=False)}\n\n"
            f"Mensagem original: {raw_response}\n\n"
            f"Melhore esta mensagem:"
        )
        return await self._call(WHATSAPP_RESPONSE_SYSTEM, prompt, max_tokens=256)
