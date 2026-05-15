import json
from typing import Any

import openai

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


class OpenAIProvider:
    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=_TIMEOUT,
        )
        self._model = settings.OPENAI_MODEL

    async def _call(
        self, system: str, user_message: str, max_tokens: int = 1024
    ) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=settings.AI_TEMPERATURE,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            )
            logger.info(
                "openai_api_call",
                model=self._model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
            return response.choices[0].message.content or ""
        except openai.RateLimitError as e:
            logger.warning("openai_rate_limit", error=str(e))
            raise AIServiceError(
                "Rate limit atingido. Tente novamente em alguns minutos."
            )
        except openai.AuthenticationError as e:
            logger.error("openai_auth_error", error=str(e))
            raise AIServiceError("Chave de API do OpenAI inválida.")
        except openai.APIError as e:
            logger.error(
                "openai_api_error",
                status_code=getattr(e, "status_code", None),
                error=str(e),
            )
            raise AIServiceError(f"Erro na API do OpenAI: {e}")

    async def classify_transaction(self, text: str) -> dict[str, Any]:
        raw = await self._call(
            CLASSIFY_TRANSACTION_SYSTEM,
            f'Classifique esta transação financeira: "{text}"',
            max_tokens=256,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("openai_json_parse_error", raw=raw[:200])
            raise AIServiceError(
                "Resposta inválida do OpenAI ao classificar transação."
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
