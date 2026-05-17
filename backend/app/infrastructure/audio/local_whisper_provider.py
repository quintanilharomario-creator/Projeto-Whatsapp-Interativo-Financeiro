"""Local Whisper provider — runs model in-process using faster-whisper.

The model is loaded once at startup and cached as a class variable so
subsequent calls reuse the in-memory model. Falls back gracefully if
faster-whisper is not installed or the model cannot be loaded.
"""

import asyncio
import os
import tempfile

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LocalWhisperProvider:
    _model = None

    def __init__(self) -> None:
        if LocalWhisperProvider._model is None:
            from faster_whisper import WhisperModel  # faster-whisper package

            size = settings.WHISPER_MODEL_SIZE
            logger.info("local_whisper_loading", size=size)
            LocalWhisperProvider._model = WhisperModel(
                size, device="cpu", compute_type="int8"
            )
            logger.info("local_whisper_ready", size=size)

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "ogg"
        loop = asyncio.get_event_loop()

        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            result = await loop.run_in_executor(None, self._transcribe_sync, tmp_path)
            logger.info(
                "local_whisper_transcription",
                size=settings.WHISPER_MODEL_SIZE,
                chars=len(result),
            )
            return result
        finally:
            os.unlink(tmp_path)

    def _transcribe_sync(self, audio_path: str) -> str:
        segments, _info = LocalWhisperProvider._model.transcribe(
            audio_path, language="pt", beam_size=5
        )
        return " ".join(seg.text.strip() for seg in segments)
