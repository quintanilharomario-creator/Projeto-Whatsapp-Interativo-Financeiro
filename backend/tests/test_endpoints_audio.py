"""Tests for audio endpoints — Whisper and WhatsApp processing are mocked."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


def _audio_file(content: bytes = b"fake audio", filename: str = "audio.ogg"):
    return {"file": (filename, io.BytesIO(content), "audio/ogg")}


async def test_transcribe_endpoint_success(client: AsyncClient, auth_headers):
    with patch(
        "app.api.v1.endpoints.audio.WhisperProvider.transcribe",
        new=AsyncMock(return_value="Gastei cinquenta reais no mercado"),
    ):
        response = await client.post(
            "/api/v1/audio/transcribe",
            files=_audio_file(),
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Gastei cinquenta reais no mercado"
    assert "size_bytes" in data


async def test_transcribe_endpoint_no_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/audio/transcribe",
        files=_audio_file(),
    )
    assert response.status_code == 403


async def test_transcribe_whatsapp_endpoint_success(
    client: AsyncClient, db: AsyncSession, test_user
):
    with (
        patch(
            "app.api.v1.endpoints.audio.WhisperProvider.transcribe",
            new=AsyncMock(return_value="Gastei R$50 no mercado"),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_ai_classify",
            new=AsyncMock(side_effect=lambda text, parsed, **kw: parsed),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_enhance_response",
            new=AsyncMock(side_effect=lambda text, *a, **kw: text),
        ),
    ):
        response = await client.post(
            "/api/v1/audio/whatsapp",
            data={"phone_number": test_user.phone or "+5511999999999"},
            files=_audio_file(),
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "message_text" in data


async def test_transcribe_whatsapp_no_auth_allowed(client: AsyncClient):
    """Audio/whatsapp endpoint does not require JWT (receives from Evolution API)."""
    with (
        patch(
            "app.api.v1.endpoints.audio.WhisperProvider.transcribe",
            new=AsyncMock(return_value="Gastei R$50"),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_ai_classify",
            new=AsyncMock(side_effect=lambda text, parsed, **kw: parsed),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_enhance_response",
            new=AsyncMock(side_effect=lambda text, *a, **kw: text),
        ),
    ):
        response = await client.post(
            "/api/v1/audio/whatsapp",
            data={"phone_number": "+5511888888888"},
            files=_audio_file(),
        )
    assert response.status_code == 201
