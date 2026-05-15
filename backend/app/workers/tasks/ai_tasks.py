import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(name="ai.analyze_transaction", bind=True, max_retries=3, default_retry_delay=60)
def analyze_transaction_task(self, text: str, user_id: str | None = None) -> dict:
    """Analyze a transaction text using AI and return classification."""
    async def _run() -> dict:
        from app.services.ai_service import AIService
        service = AIService()
        suggestion = await service.analyze_transaction(text, user_id=user_id)
        return {
            "type": suggestion.type.value,
            "category": suggestion.category,
            "amount": str(suggestion.amount) if suggestion.amount else None,
            "confidence": suggestion.confidence,
            "explanation": suggestion.explanation,
        }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="ai.monthly_report", bind=True, max_retries=2, default_retry_delay=120)
def generate_monthly_report_task(self, user_id: str) -> dict:
    """Generate AI monthly financial report for a user."""
    async def _run() -> dict:
        from app.infrastructure.database.session import AsyncSessionLocal
        from app.services.ai_service import AIService
        async with AsyncSessionLocal() as db:
            service = AIService()
            return await service.generate_monthly_report(user_id=user_id, db=db)

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
