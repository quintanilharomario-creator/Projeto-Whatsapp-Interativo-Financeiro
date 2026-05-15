"""Unit tests for Celery tasks — all external calls are mocked."""
import asyncio
import base64
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Helper: close coroutine before returning to silence RuntimeWarning
def _close_coro(return_value):
    def _side_effect(coro):
        coro.close()
        return return_value
    return _side_effect


def test_celery_app_configured():
    from app.workers.celery_app import celery_app
    assert celery_app.conf.task_serializer == "json"
    assert "ai.*" in celery_app.conf.task_routes
    assert "whatsapp.*" in celery_app.conf.task_routes
    assert "audio.*" in celery_app.conf.task_routes


# ── analyze_transaction_task ──────────────────────────────────────────────

def test_analyze_transaction_task_success():
    from app.workers.tasks.ai_tasks import analyze_transaction_task

    expected = {
        "type": "EXPENSE",
        "category": "Alimentação",
        "amount": None,
        "confidence": 0.95,
        "explanation": "Compra em mercado",
    }
    with patch("app.workers.tasks.ai_tasks.asyncio.run", side_effect=_close_coro(expected)):
        result = analyze_transaction_task.run("Gastei R$50 no mercado")

    assert result["type"] == "EXPENSE"
    assert result["category"] == "Alimentação"
    assert result["confidence"] == 0.95


def test_analyze_transaction_task_retries_on_error():
    from app.workers.tasks.ai_tasks import analyze_transaction_task

    def _raise(coro):
        coro.close()
        raise Exception("timeout")

    with patch("app.workers.tasks.ai_tasks.asyncio.run", side_effect=_raise):
        with pytest.raises(Exception):
            analyze_transaction_task.run("texto")


def test_analyze_transaction_task_inner_run():
    """Covers the _run() coroutine body by mocking AIService directly."""
    from app.workers.tasks.ai_tasks import analyze_transaction_task

    mock_suggestion = MagicMock()
    mock_suggestion.type.value = "EXPENSE"
    mock_suggestion.category = "Alimentação"
    mock_suggestion.amount = Decimal("50.00")
    mock_suggestion.confidence = 0.92
    mock_suggestion.explanation = "Mercado"

    with patch("app.services.ai_service.AIService") as MockAI:
        MockAI.return_value.analyze_transaction = AsyncMock(return_value=mock_suggestion)
        result = analyze_transaction_task.run("Gastei R$50 no mercado")

    assert result["type"] == "EXPENSE"
    assert result["amount"] == "50.00"


def test_generate_monthly_report_task_with_mocked_return():
    """Quick smoke test via asyncio.run mock."""
    from app.workers.tasks.ai_tasks import generate_monthly_report_task

    expected = {"summary": "Gastou muito este mês", "total_expense": "500.00"}
    with patch("app.workers.tasks.ai_tasks.asyncio.run", side_effect=_close_coro(expected)):
        result = generate_monthly_report_task.run("user-uuid-123")

    assert result == expected


def test_generate_monthly_report_task_inner_run():
    """Covers generate_monthly_report_task._run() body by mocking inner deps."""
    from unittest.mock import MagicMock
    from app.workers.tasks.ai_tasks import generate_monthly_report_task

    expected = {"narrative": "Mês equilibrado", "total": "1000.00"}
    mock_db = MagicMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.infrastructure.database.session.AsyncSessionLocal", return_value=mock_session_cm), \
         patch("app.services.ai_service.AIService") as MockAI:
        MockAI.return_value.generate_monthly_report = AsyncMock(return_value=expected)
        result = generate_monthly_report_task.run("user-uuid-123")

    assert result == expected


def test_generate_monthly_report_task_retry_on_error():
    """Covers the except/retry path of generate_monthly_report_task."""
    from app.workers.tasks.ai_tasks import generate_monthly_report_task

    def _raise(coro):
        coro.close()
        raise Exception("db timeout")

    with patch("app.workers.tasks.ai_tasks.asyncio.run", side_effect=_raise):
        with pytest.raises(Exception):
            generate_monthly_report_task.run("user-uuid-123")


# ── process_whatsapp_message_task ─────────────────────────────────────────

def test_process_whatsapp_message_task_success():
    from app.workers.tasks.whatsapp_tasks import process_whatsapp_message_task

    fake_id = "123e4567-e89b-12d3-a456-426614174000"
    with patch(
        "app.workers.tasks.whatsapp_tasks.asyncio.run",
        side_effect=_close_coro(fake_id),
    ):
        result = process_whatsapp_message_task.run("+5511999999999", "Gastei R$50")

    assert result == fake_id


def test_process_whatsapp_message_task_inner_run():
    """Covers the _run() body of process_whatsapp_message_task."""
    from app.workers.tasks.whatsapp_tasks import process_whatsapp_message_task

    fake_msg = MagicMock()
    fake_msg.id = "abc-def-123"

    with patch("app.infrastructure.database.session.AsyncSessionLocal") as MockSession, \
         patch("app.services.whatsapp_service.WhatsappService.receive_message", new_callable=AsyncMock) as mock_recv:
        mock_recv.return_value = fake_msg
        MockSession.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        MockSession.return_value.__aexit__ = AsyncMock(return_value=False)

        result = process_whatsapp_message_task.run("+5511999999999", "Gastei R$50")

    assert result == "abc-def-123"


def test_process_whatsapp_message_task_retries_on_error():
    from app.workers.tasks.whatsapp_tasks import process_whatsapp_message_task

    def _raise(coro):
        coro.close()
        raise Exception("db error")

    with patch("app.workers.tasks.whatsapp_tasks.asyncio.run", side_effect=_raise):
        with pytest.raises(Exception):
            process_whatsapp_message_task.run("+5511999999999", "Gastei R$50")


# ── transcribe_audio_task ─────────────────────────────────────────────────

def test_transcribe_audio_task_success():
    from app.workers.tasks.audio_tasks import transcribe_audio_task

    audio_b64 = base64.b64encode(b"fake audio bytes").decode()
    with patch(
        "app.workers.tasks.audio_tasks.asyncio.run",
        side_effect=_close_coro("Gastei cinquenta reais"),
    ):
        result = transcribe_audio_task.run(audio_b64)

    assert result == "Gastei cinquenta reais"


def test_transcribe_audio_task_retry_on_error():
    """Covers the except/retry path of transcribe_audio_task (lines 18-19)."""
    from app.workers.tasks.audio_tasks import transcribe_audio_task

    def _raise(coro):
        coro.close()
        raise Exception("api error")

    audio_b64 = base64.b64encode(b"bytes").decode()
    with patch("app.workers.tasks.audio_tasks.asyncio.run", side_effect=_raise):
        with pytest.raises(Exception):
            transcribe_audio_task.run(audio_b64)


def test_transcribe_audio_task_inner_run():
    """Covers transcribe_audio_task._run() body."""
    from app.workers.tasks.audio_tasks import transcribe_audio_task

    audio_b64 = base64.b64encode(b"fake audio bytes").decode()

    with patch("app.infrastructure.audio.whisper_provider.WhisperProvider") as MockWhisper:
        MockWhisper.return_value.transcribe = AsyncMock(return_value="texto transcrito")
        result = transcribe_audio_task.run(audio_b64, filename="audio.mp3")

    assert result == "texto transcrito"


# ── transcribe_and_process_task ───────────────────────────────────────────

def test_transcribe_and_process_task_success():
    from app.workers.tasks.audio_tasks import transcribe_and_process_task

    audio_b64 = base64.b64encode(b"fake audio bytes").decode()
    fake_id = "123e4567-e89b-12d3-a456-426614174000"
    with patch(
        "app.workers.tasks.audio_tasks.asyncio.run",
        side_effect=_close_coro(fake_id),
    ):
        result = transcribe_and_process_task.run(audio_b64, "+5511999999999")

    assert result == fake_id


def test_transcribe_and_process_task_retry_on_error():
    """Covers the except/retry path of transcribe_and_process_task (lines 51-52)."""
    from app.workers.tasks.audio_tasks import transcribe_and_process_task

    def _raise(coro):
        coro.close()
        raise Exception("whisper unavailable")

    audio_b64 = base64.b64encode(b"bytes").decode()
    with patch("app.workers.tasks.audio_tasks.asyncio.run", side_effect=_raise):
        with pytest.raises(Exception):
            transcribe_and_process_task.run(audio_b64, "+5511999999999")


def test_transcribe_and_process_task_inner_run():
    """Covers transcribe_and_process_task._run() body."""
    from app.workers.tasks.audio_tasks import transcribe_and_process_task

    audio_b64 = base64.b64encode(b"fake audio bytes").decode()
    fake_msg = MagicMock()
    fake_msg.id = "xyz-999"

    with patch("app.infrastructure.audio.whisper_provider.WhisperProvider") as MockWhisper, \
         patch("app.infrastructure.database.session.AsyncSessionLocal") as MockSession, \
         patch("app.services.whatsapp_service.WhatsappService.receive_message", new_callable=AsyncMock) as mock_recv:
        MockWhisper.return_value.transcribe = AsyncMock(return_value="Gastei R$30 no café")
        mock_recv.return_value = fake_msg
        MockSession.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        MockSession.return_value.__aexit__ = AsyncMock(return_value=False)

        result = transcribe_and_process_task.run(audio_b64, "+5511999999999", filename="audio.ogg")

    assert result == "xyz-999"
