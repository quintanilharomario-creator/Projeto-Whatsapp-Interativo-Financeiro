"""Tests for WhatsApp audio message handling (download → Whisper → process)."""

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as _settings
from app.core.exceptions import AIServiceError


# ── helpers ───────────────────────────────────────────────────────────────────


def _audio_payload(phone: str, media_id: str = "MEDIA_ID_123") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": phone,
                                    "id": "wamid.audio.test",
                                    "timestamp": "1234567890",
                                    "type": "audio",
                                    "audio": {
                                        "id": media_id,
                                        "mime_type": "audio/ogg; codecs=opus",
                                    },
                                }
                            ]
                        },
                        "field": "messages",
                    }
                ]
            }
        ],
    }


@pytest_asyncio.fixture
async def user_with_phone_audio(db: AsyncSession):
    from app.services.auth_service import AuthService

    user = await AuthService.register(
        email="audio_test@test.com",
        password="TestPass123!",
        full_name="Audio Test User",
        db=db,
    )
    user.phone = "+5511666666666"
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── endpoint tests ─────────────────────────────────────────────────────────────


async def test_webhook_audio_success_stores_message(
    client: AsyncClient, user_with_phone_audio
):
    """Full flow: audio webhook → download → transcribe → message stored in DB."""
    transcribed = "Gastei R$80 no supermercado"

    with (
        patch.object(_settings, "OPENAI_API_KEY", "test-key-for-audio"),
        patch(
            "app.api.v1.endpoints.whatsapp.download_audio",
            new=AsyncMock(return_value=b"x" * 4000),
        ),
        patch(
            "app.infrastructure.audio.whisper_provider.WhisperProvider.transcribe",
            new=AsyncMock(return_value=transcribed),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ),
    ):
        response = await client.post(
            "/api/v1/whatsapp/webhook", json=_audio_payload("+5511666666666")
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511666666666"}
    )
    data = msgs.json()
    assert len(data) == 1
    assert data[0]["message_text"] == transcribed
    assert data[0]["message_type"] == "EXPENSE"
    assert data[0]["extracted_amount"] == "80.00"
    assert data[0]["transaction_id"] is not None


async def test_webhook_audio_missing_audio_field_is_skipped(client: AsyncClient):
    """Audio message without audio.id field is silently skipped (no DB record)."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "+5511555555555",
                                    "id": "wamid.audio.no_id",
                                    "timestamp": "1234567890",
                                    "type": "audio",
                                    # no "audio" field — should be skipped
                                }
                            ]
                        },
                        "field": "messages",
                    }
                ]
            }
        ],
    }
    response = await client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511555555555"}
    )
    assert msgs.json() == []


async def test_webhook_audio_download_failure_sends_fallback(client: AsyncClient):
    """When media download fails, a friendly reply is sent and webhook returns 200."""
    with (
        patch.object(_settings, "OPENAI_API_KEY", "test-key-for-audio"),
        patch(
            "app.api.v1.endpoints.whatsapp.download_audio",
            new=AsyncMock(side_effect=Exception("Connection timeout")),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ) as mock_reply,
    ):
        response = await client.post(
            "/api/v1/whatsapp/webhook", json=_audio_payload("+5511444444444")
        )

    assert response.status_code == 200
    mock_reply.assert_called_once()
    assert "áudio" in mock_reply.call_args[0][1].lower()


async def test_webhook_audio_transcription_failure_fallback(
    client: AsyncClient, db: AsyncSession
):
    """Whisper error → fallback message stored in DB, friendly reply sent.

    Two _try_send_reply calls are expected: the immediate ack ("Recebi seu áudio!")
    sent in the endpoint, and the fallback error sent inside transcribe_and_process.
    """
    with (
        patch.object(_settings, "OPENAI_API_KEY", "test-key-for-audio"),
        patch(
            "app.api.v1.endpoints.whatsapp.download_audio",
            new=AsyncMock(return_value=b"x" * 4000),
        ),
        patch(
            "app.infrastructure.audio.whisper_provider.WhisperProvider.transcribe",
            new=AsyncMock(side_effect=AIServiceError("rate limit")),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ) as mock_reply,
    ):
        response = await client.post(
            "/api/v1/whatsapp/webhook", json=_audio_payload("+5511333333333")
        )

    assert response.status_code == 200

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511333333333"}
    )
    data = msgs.json()
    assert len(data) == 1
    assert "transcrição falhou" in data[0]["message_text"]
    assert data[0]["message_type"] == "OTHER"
    # ack ("Recebi seu áudio!") + fallback error = 2 calls
    assert mock_reply.call_count == 2
    assert "áudio" in mock_reply.call_args[0][1].lower()


async def test_webhook_audio_no_openai_key_fallback(
    client: AsyncClient, db: AsyncSession
):
    """Without OPENAI_API_KEY, audio is rejected with a friendly stored message."""
    with (
        patch.object(_settings, "OPENAI_API_KEY", ""),
        patch(
            "app.api.v1.endpoints.whatsapp.download_audio",
            new=AsyncMock(return_value=b"audio-bytes"),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ),
    ):
        response = await client.post(
            "/api/v1/whatsapp/webhook", json=_audio_payload("+5511222222222")
        )

    assert response.status_code == 200

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511222222222"}
    )
    data = msgs.json()
    assert len(data) == 1
    assert "OPENAI_API_KEY" in data[0]["message_text"]
    assert data[0]["message_type"] == "OTHER"


# ── unit tests for transcribe_and_process ─────────────────────────────────────


async def test_transcribe_and_process_success(db: AsyncSession):
    """transcribe_and_process: happy path returns a WhatsappMessage with transcribed text."""
    from app.services.whatsapp_service import WhatsappService

    with (
        patch.object(_settings, "OPENAI_API_KEY", "test-key-for-audio"),
        patch(
            "app.infrastructure.audio.whisper_provider.WhisperProvider.transcribe",
            new=AsyncMock(return_value="Recebi R$500 de freelance"),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ),
    ):
        msg = await WhatsappService.transcribe_and_process(
            phone_number="+5511000000001",
            audio_bytes=b"x" * 4000,
            db=db,
        )

    assert msg.message_text == "Recebi R$500 de freelance"
    assert msg.phone_number == "+5511000000001"
    assert "🎤 Entendi:" in (msg.response_text or "")


async def test_transcribe_and_process_whisper_error_returns_fallback(db: AsyncSession):
    """transcribe_and_process: Whisper error → fallback WhatsappMessage stored."""
    from app.services.whatsapp_service import WhatsappService

    with (
        patch.object(_settings, "OPENAI_API_KEY", "test-key-for-audio"),
        patch(
            "app.infrastructure.audio.whisper_provider.WhisperProvider.transcribe",
            new=AsyncMock(side_effect=AIServiceError("auth error")),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ),
    ):
        msg = await WhatsappService.transcribe_and_process(
            phone_number="+5511000000002",
            audio_bytes=b"x" * 4000,
            db=db,
        )

    assert "transcrição falhou" in msg.message_text
    assert msg.phone_number == "+5511000000002"
    assert "áudio" in (msg.response_text or "").lower()


async def test_transcribe_and_process_audio_too_short(db: AsyncSession):
    """Audio < 3 KB triggers friendly rejection without calling Whisper."""
    from app.services.whatsapp_service import WhatsappService

    with (
        patch.object(_settings, "OPENAI_API_KEY", "test-key-for-audio"),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ) as mock_reply,
    ):
        msg = await WhatsappService.transcribe_and_process(
            phone_number="+5511000000003",
            audio_bytes=b"short",
            db=db,
        )

    assert "muito curto" in msg.message_text
    assert "microfone" in (msg.response_text or "").lower()
    mock_reply.assert_called_once()


async def test_webhook_audio_short_audio_detected(client: AsyncClient):
    """Small audio bytes from webhook trigger 'too short' reply, no DB transaction."""
    with (
        patch.object(_settings, "OPENAI_API_KEY", "test-key-for-audio"),
        patch(
            "app.api.v1.endpoints.whatsapp.download_audio",
            new=AsyncMock(return_value=b"tiny"),
        ),
        patch(
            "app.services.whatsapp_service.WhatsappService._try_send_reply",
            new=AsyncMock(),
        ) as mock_reply,
    ):
        response = await client.post(
            "/api/v1/whatsapp/webhook", json=_audio_payload("+5511100000001")
        )

    assert response.status_code == 200
    # ack ("Recebi seu áudio!") + too-short rejection = 2 calls
    assert mock_reply.call_count == 2
    short_reply_text = mock_reply.call_args_list[1][0][1]
    assert "microfone" in short_reply_text.lower()
