"""Unit tests for Celery tasks — all external calls are mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_celery_app_configured():
    from app.workers.celery_app import celery_app
    assert celery_app.conf.task_serializer == "json"
    assert "ai.*" in celery_app.conf.task_routes
    assert "whatsapp.*" in celery_app.conf.task_routes
    assert "audio.*" in celery_app.conf.task_routes


def test_analyze_transaction_task_success():
    from app.workers.tasks.ai_tasks import analyze_transaction_task

    mock_suggestion = MagicMock()
    mock_suggestion.type.value = "EXPENSE"
    mock_suggestion.category = "Alimentação"
    mock_suggestion.amount = None
    mock_suggestion.confidence = 0.95
    mock_suggestion.explanation = "Compra em mercado"

    with patch("app.workers.tasks.ai_tasks.asyncio.run") as mock_run:
        mock_run.return_value = {
            "type": "EXPENSE",
            "category": "Alimentação",
            "amount": None,
            "confidence": 0.95,
            "explanation": "Compra em mercado",
        }
        result = analyze_transaction_task.run("Gastei R$50 no mercado")

    assert result["type"] == "EXPENSE"
    assert result["category"] == "Alimentação"
    assert result["confidence"] == 0.95


def test_analyze_transaction_task_retries_on_error():
    from app.workers.tasks.ai_tasks import analyze_transaction_task

    with patch("app.workers.tasks.ai_tasks.asyncio.run", side_effect=Exception("timeout")):
        with pytest.raises(Exception):
            analyze_transaction_task.run("texto")


def test_process_whatsapp_message_task_success():
    from app.workers.tasks.whatsapp_tasks import process_whatsapp_message_task

    fake_id = "123e4567-e89b-12d3-a456-426614174000"
    with patch("app.workers.tasks.whatsapp_tasks.asyncio.run", return_value=fake_id):
        result = process_whatsapp_message_task.run("+5511999999999", "Gastei R$50")

    assert result == fake_id


def test_transcribe_audio_task_success():
    import base64
    from app.workers.tasks.audio_tasks import transcribe_audio_task

    audio_b64 = base64.b64encode(b"fake audio bytes").decode()
    with patch("app.workers.tasks.audio_tasks.asyncio.run", return_value="Gastei cinquenta reais"):
        result = transcribe_audio_task.run(audio_b64)

    assert result == "Gastei cinquenta reais"


def test_transcribe_and_process_task_success():
    import base64
    from app.workers.tasks.audio_tasks import transcribe_and_process_task

    audio_b64 = base64.b64encode(b"fake audio bytes").decode()
    fake_id = "123e4567-e89b-12d3-a456-426614174000"
    with patch("app.workers.tasks.audio_tasks.asyncio.run", return_value=fake_id):
        result = transcribe_and_process_task.run(audio_b64, "+5511999999999")

    assert result == fake_id
