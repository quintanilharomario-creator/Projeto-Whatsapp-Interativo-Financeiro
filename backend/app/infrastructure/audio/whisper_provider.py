import io

import openai

from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_SUPPORTED_FORMATS = {
    "flac",
    "m4a",
    "mp3",
    "mp4",
    "mpeg",
    "mpga",
    "oga",
    "ogg",
    "wav",
    "webm",
}


class WhisperProvider:
    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=60.0,
        )
        self._model = settings.WHISPER_MODEL

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "ogg"
        if ext not in _SUPPORTED_FORMATS:
            raise AIServiceError(
                f"Formato de áudio não suportado: {ext}. "
                f"Use: {', '.join(sorted(_SUPPORTED_FORMATS))}"
            )

        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename

            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
                language="pt",
                response_format="text",
            )
            text = response if isinstance(response, str) else response.text
            logger.info(
                "whisper_transcription",
                model=self._model,
                filename=filename,
                chars=len(text),
            )
            return text.strip()
        except openai.RateLimitError as e:
            logger.warning("whisper_rate_limit", error=str(e))
            raise AIServiceError(
                "Rate limit atingido no Whisper. Tente novamente em alguns minutos."
            )
        except openai.AuthenticationError as e:
            logger.error("whisper_auth_error", error=str(e))
            raise AIServiceError(
                "Chave de API do OpenAI inválida para transcrição de áudio."
            )
        except openai.APIError as e:
            logger.error(
                "whisper_api_error",
                status_code=getattr(e, "status_code", None),
                error=str(e),
            )
            raise AIServiceError(f"Erro na transcrição de áudio: {e}")
