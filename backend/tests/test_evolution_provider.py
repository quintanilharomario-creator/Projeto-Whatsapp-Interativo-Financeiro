"""Tests for EvolutionProvider (httpx calls mocked)."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _mock_http_client(status_code: int, json_data: dict | None = None, text: str = ""):
    """Build a mock httpx response + context-manager client."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.text = text
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.get = AsyncMock(return_value=mock_resp)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_cm, mock_resp, mock_client


# ── create_instance ───────────────────────────────────────────────────────

async def test_create_instance_success():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    data = {"instance": {"instanceName": "saas_bot", "status": "created"}}
    mock_cm, _, _ = _mock_http_client(200, data)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.create_instance("saas_bot")

    assert result == data


async def test_create_instance_uses_default_name():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    data = {"instance": {"instanceName": "default_instance"}}
    mock_cm, _, mock_client = _mock_http_client(200, data)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.create_instance()

    # Verify request was made (default instance name from settings)
    assert mock_client.post.called
    assert result == data


# ── get_qr_code ───────────────────────────────────────────────────────────

async def test_get_qr_code_success():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    data = {"base64": "iVBORw0KGgoAAAA...", "count": 1}
    mock_cm, _, _ = _mock_http_client(200, data)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.get_qr_code("saas_bot")

    assert result["base64"].startswith("iVBOR")


async def test_get_qr_code_uses_default_name():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    data = {"base64": "abc123", "count": 0}
    mock_cm, _, mock_client = _mock_http_client(200, data)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.get_qr_code()

    assert mock_client.get.called
    assert result == data


# ── get_instance_status ───────────────────────────────────────────────────

async def test_get_instance_status_open():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    data = {"instance": {"instanceName": "saas_bot", "state": "open"}}
    mock_cm, _, _ = _mock_http_client(200, data)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.get_instance_status()

    assert result["instance"]["state"] == "open"


async def test_get_instance_status_uses_provided_name():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    data = {"instance": {"instanceName": "custom", "state": "connecting"}}
    mock_cm, _, mock_client = _mock_http_client(200, data)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.get_instance_status("custom")

    assert mock_client.get.called
    url_called = mock_client.get.call_args[0][0]
    assert "custom" in url_called


# ── send_message ──────────────────────────────────────────────────────────

async def test_send_message_success_returns_true():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    mock_cm, _, _ = _mock_http_client(201, {"key": {"id": "wamid.abc"}})

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.send_message("+5511999999999", "Olá!")

    assert result is True


async def test_send_message_strips_plus_from_number():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    mock_cm, _, mock_client = _mock_http_client(201, {})

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        await provider.send_message("+5511999999999", "Teste")

    payload = mock_client.post.call_args[1]["json"]
    assert payload["number"] == "5511999999999"


async def test_send_message_strips_whatsapp_net_suffix():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    mock_cm, _, mock_client = _mock_http_client(201, {})

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        await provider.send_message("5511999999999@s.whatsapp.net", "Teste")

    payload = mock_client.post.call_args[1]["json"]
    assert "@" not in payload["number"]


async def test_send_message_non_201_returns_false():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    mock_cm, _, _ = _mock_http_client(400, {}, text="Bad Request")

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.send_message("+5511999999999", "Olá!")

    assert result is False


async def test_send_message_http_error_returns_false():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.send_message("+5511999999999", "Olá!")

    assert result is False


async def test_send_message_uses_default_instance():
    from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider

    mock_cm, _, mock_client = _mock_http_client(201, {})

    with patch("httpx.AsyncClient", return_value=mock_cm):
        provider = EvolutionProvider()
        result = await provider.send_message("+5511000000000", "Hello")

    # URL should contain the default instance name from settings
    url = mock_client.post.call_args[0][0]
    assert "sendText" in url
    assert result is True
