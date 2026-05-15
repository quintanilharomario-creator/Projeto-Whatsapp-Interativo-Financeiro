"""Tests for WhisperProvider — OpenAI calls are mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from app.core.exceptions import AIServiceError


@pytest.fixture
def mock_openai_client():
    with patch("app.infrastructure.audio.whisper_provider.openai.AsyncOpenAI") as MockClass:
        mock_client = MagicMock()
        MockClass.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
async def test_transcribe_success(mock_openai_client):
    from app.infrastructure.audio.whisper_provider import WhisperProvider

    mock_openai_client.audio.transcriptions.create = AsyncMock(
        return_value="Gastei cinquenta reais no mercado"
    )

    provider = WhisperProvider()
    result = await provider.transcribe(b"fake audio bytes", filename="audio.ogg")

    assert result == "Gastei cinquenta reais no mercado"
    mock_openai_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_openai_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["language"] == "pt"
    assert call_kwargs["model"] is not None


@pytest.mark.asyncio
async def test_transcribe_strips_whitespace(mock_openai_client):
    from app.infrastructure.audio.whisper_provider import WhisperProvider

    mock_openai_client.audio.transcriptions.create = AsyncMock(
        return_value="  Recebi salário  \n"
    )

    provider = WhisperProvider()
    result = await provider.transcribe(b"fake audio bytes")

    assert result == "Recebi salário"


@pytest.mark.asyncio
async def test_transcribe_unsupported_format(mock_openai_client):
    from app.infrastructure.audio.whisper_provider import WhisperProvider

    provider = WhisperProvider()
    with pytest.raises(AIServiceError, match="não suportado"):
        await provider.transcribe(b"fake bytes", filename="audio.txt")


@pytest.mark.asyncio
async def test_transcribe_rate_limit_error(mock_openai_client):
    from app.infrastructure.audio.whisper_provider import WhisperProvider

    mock_openai_client.audio.transcriptions.create = AsyncMock(
        side_effect=openai.RateLimitError(
            message="rate limit", response=MagicMock(status_code=429), body={}
        )
    )

    provider = WhisperProvider()
    with pytest.raises(AIServiceError, match="Rate limit"):
        await provider.transcribe(b"fake audio bytes")


@pytest.mark.asyncio
async def test_transcribe_auth_error(mock_openai_client):
    from app.infrastructure.audio.whisper_provider import WhisperProvider

    mock_openai_client.audio.transcriptions.create = AsyncMock(
        side_effect=openai.AuthenticationError(
            message="invalid key", response=MagicMock(status_code=401), body={}
        )
    )

    provider = WhisperProvider()
    with pytest.raises(AIServiceError, match="inválida"):
        await provider.transcribe(b"fake audio bytes")


@pytest.mark.asyncio
async def test_transcribe_accepts_mp3(mock_openai_client):
    from app.infrastructure.audio.whisper_provider import WhisperProvider

    mock_openai_client.audio.transcriptions.create = AsyncMock(return_value="texto")

    provider = WhisperProvider()
    result = await provider.transcribe(b"mp3 bytes", filename="audio.mp3")
    assert result == "texto"
