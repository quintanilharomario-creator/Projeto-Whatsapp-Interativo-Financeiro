import asyncio
import base64

from app.workers.celery_app import celery_app


@celery_app.task(
    name="audio.transcribe", bind=True, max_retries=2, default_retry_delay=60
)
def transcribe_audio_task(self, audio_b64: str, filename: str = "audio.ogg") -> str:
    """Transcribe base64-encoded audio bytes and return the transcribed text."""

    async def _run() -> str:
        from app.infrastructure.audio.whisper_provider import WhisperProvider

        audio_bytes = base64.b64decode(audio_b64)
        provider = WhisperProvider()
        return await provider.transcribe(audio_bytes, filename=filename)

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="audio.transcribe_and_process",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def transcribe_and_process_task(
    self, audio_b64: str, phone_number: str, filename: str = "audio.ogg"
) -> str:
    """Transcribe audio then process as WhatsApp message. Returns WhatsappMessage UUID."""

    async def _run() -> str:
        from app.infrastructure.audio.whisper_provider import WhisperProvider
        from app.infrastructure.database.session import AsyncSessionLocal
        from app.services.whatsapp_service import WhatsappService

        audio_bytes = base64.b64decode(audio_b64)
        provider = WhisperProvider()
        text = await provider.transcribe(audio_bytes, filename=filename)

        async with AsyncSessionLocal() as db:
            msg = await WhatsappService.receive_message(
                phone_number=phone_number,
                message_text=text,
                db=db,
            )
            return str(msg.id)

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
