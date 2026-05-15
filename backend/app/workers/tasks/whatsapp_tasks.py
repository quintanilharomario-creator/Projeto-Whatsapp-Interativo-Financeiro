import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(
    name="whatsapp.process_message", bind=True, max_retries=3, default_retry_delay=30
)
def process_whatsapp_message_task(self, phone_number: str, message_text: str) -> str:
    """Process an incoming WhatsApp message asynchronously.

    Returns the UUID of the created WhatsappMessage record.
    """

    async def _run() -> str:
        from app.infrastructure.database.session import AsyncSessionLocal
        from app.services.whatsapp_service import WhatsappService

        async with AsyncSessionLocal() as db:
            msg = await WhatsappService.receive_message(
                phone_number=phone_number,
                message_text=message_text,
                db=db,
            )
            return str(msg.id)

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
