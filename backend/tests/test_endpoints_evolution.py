"""Tests for /api/v1/evolution endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ── Instance endpoints ─────────────────────────────────────────────────────

async def test_create_instance_success(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.create_instance",
               new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {"instanceName": "saas_bot", "status": "created"}
        response = await client.post("/api/v1/evolution/instance/create")

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "created"
    assert "instance" in data


async def test_create_instance_provider_error(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.create_instance",
               side_effect=Exception("Evolution API unavailable")):
        response = await client.post("/api/v1/evolution/instance/create")

    assert response.status_code == 502
    assert "Evolution API unavailable" in response.json()["detail"]


async def test_get_qr_code_success(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.get_qr_code",
               new_callable=AsyncMock) as mock_qr:
        mock_qr.return_value = {"base64": "iVBORabc123", "count": 1}
        response = await client.get("/api/v1/evolution/instance/qrcode")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["base64"] == "iVBORabc123"


async def test_get_qr_code_not_ready(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.get_qr_code",
               new_callable=AsyncMock) as mock_qr:
        mock_qr.return_value = {"count": 0}  # no base64 key
        response = await client.get("/api/v1/evolution/instance/qrcode")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "waiting"


async def test_get_qr_code_provider_error(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.get_qr_code",
               side_effect=Exception("timeout")):
        response = await client.get("/api/v1/evolution/instance/qrcode")

    assert response.status_code == 502


async def test_get_instance_status_connected(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.get_instance_status",
               new_callable=AsyncMock) as mock_status:
        mock_status.return_value = {
            "instance": {"instanceName": "saas_bot", "state": "open"}
        }
        response = await client.get("/api/v1/evolution/instance/status")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["state"] == "open"


async def test_get_instance_status_disconnected(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.get_instance_status",
               new_callable=AsyncMock) as mock_status:
        mock_status.return_value = {
            "instance": {"instanceName": "saas_bot", "state": "close"}
        }
        response = await client.get("/api/v1/evolution/instance/status")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False


async def test_get_instance_status_provider_error(client: AsyncClient):
    with patch("app.infrastructure.whatsapp.evolution_provider.EvolutionProvider.get_instance_status",
               side_effect=Exception("network error")):
        response = await client.get("/api/v1/evolution/instance/status")

    assert response.status_code == 502


# ── Evolution webhook ──────────────────────────────────────────────────────

def _evolution_payload(
    phone: str,
    text: str,
    event: str = "messages.upsert",
    from_me: bool = False,
) -> dict:
    return {
        "event": event,
        "instance": "saas_bot",
        "data": {
            "key": {"remoteJid": f"{phone}@s.whatsapp.net", "fromMe": from_me, "id": "wamid.abc"},
            "message": {"conversation": text},
            "messageType": "conversation",
            "pushName": "Test User",
        },
    }


async def test_evolution_webhook_processes_message(client: AsyncClient):
    with patch("app.services.whatsapp_service.WhatsappService.receive_message",
               new_callable=AsyncMock) as mock_recv:
        mock_msg = MagicMock()
        mock_msg.id = "msg-uuid-123"
        mock_recv.return_value = mock_msg

        response = await client.post(
            "/api/v1/evolution/webhook",
            json=_evolution_payload("+5511888888888", "Gastei R$50 no mercado"),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_recv.assert_called_once()


async def test_evolution_webhook_ignores_outbound(client: AsyncClient):
    response = await client.post(
        "/api/v1/evolution/webhook",
        json=_evolution_payload("+5511888888888", "Outbound msg", from_me=True),
    )
    assert response.status_code == 200
    assert response.json()["reason"] == "outbound"


async def test_evolution_webhook_ignores_non_upsert_event(client: AsyncClient):
    payload = _evolution_payload("+5511888888888", "anything")
    payload["event"] = "connection.update"
    response = await client.post("/api/v1/evolution/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_evolution_webhook_ignores_non_text_message(client: AsyncClient):
    payload = {
        "event": "messages.upsert",
        "instance": "saas_bot",
        "data": {
            "key": {"remoteJid": "5511@s.whatsapp.net", "fromMe": False, "id": "wamid.x"},
            "message": None,  # no text content
            "messageType": "imageMessage",
            "pushName": "User",
        },
    }
    response = await client.post("/api/v1/evolution/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["reason"] == "non-text message"


async def test_evolution_webhook_strips_whatsapp_net_suffix(client: AsyncClient):
    with patch("app.services.whatsapp_service.WhatsappService.receive_message",
               new_callable=AsyncMock) as mock_recv:
        mock_msg = MagicMock()
        mock_msg.id = "uuid"
        mock_recv.return_value = mock_msg

        await client.post(
            "/api/v1/evolution/webhook",
            json=_evolution_payload("5511888888888", "Gastei R$10"),
        )

    call_kwargs = mock_recv.call_args[1]
    assert "@" not in call_kwargs["phone_number"]
    assert call_kwargs["phone_number"] == "5511888888888"


async def test_evolution_webhook_extended_text_message(client: AsyncClient):
    """Covers the extendedTextMessage branch of _extract_text."""
    payload = {
        "event": "messages.upsert",
        "instance": "saas_bot",
        "data": {
            "key": {"remoteJid": "5511888888888@s.whatsapp.net", "fromMe": False, "id": "w"},
            "message": {
                "conversation": None,
                "extendedTextMessage": {"text": "Recebi R$500 de freelance"},
            },
            "messageType": "extendedTextMessage",
            "pushName": "User",
        },
    }
    with patch("app.services.whatsapp_service.WhatsappService.receive_message",
               new_callable=AsyncMock) as mock_recv:
        mock_msg = MagicMock()
        mock_msg.id = "uuid"
        mock_recv.return_value = mock_msg
        response = await client.post("/api/v1/evolution/webhook", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    call_kwargs = mock_recv.call_args[1]
    assert call_kwargs["message_text"] == "Recebi R$500 de freelance"
