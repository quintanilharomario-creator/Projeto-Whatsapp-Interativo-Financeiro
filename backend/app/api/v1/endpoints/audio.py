from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.infrastructure.audio.whisper_provider import WhisperProvider
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.whatsapp import WhatsappMessageResponse
from app.services.whatsapp_service import WhatsappService

router = APIRouter(prefix="/audio", tags=["Áudio"])


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(
        ..., description="Arquivo de áudio (ogg, mp3, wav, m4a, etc.)"
    ),
    current_user: User = Depends(get_current_user),
):
    """Transcribe an audio file to text using Whisper."""
    audio_bytes = await file.read()
    provider = WhisperProvider()
    text = await provider.transcribe(audio_bytes, filename=file.filename or "audio.ogg")
    return {"text": text, "filename": file.filename, "size_bytes": len(audio_bytes)}


@router.post("/whatsapp", response_model=WhatsappMessageResponse, status_code=201)
async def transcribe_and_process(
    file: UploadFile = File(
        ..., description="Áudio do WhatsApp para transcrever e processar"
    ),
    phone_number: str = Form(..., min_length=5, max_length=20),
    db: AsyncSession = Depends(get_db),
):
    """Transcribe audio and process it as a WhatsApp message.

    Useful for forwarding WhatsApp voice messages received via the Evolution API.
    """
    audio_bytes = await file.read()
    provider = WhisperProvider()
    text = await provider.transcribe(audio_bytes, filename=file.filename or "audio.ogg")
    return await WhatsappService.receive_message(
        phone_number=phone_number,
        message_text=text,
        db=db,
    )
