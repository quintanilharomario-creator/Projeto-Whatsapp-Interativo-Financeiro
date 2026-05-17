"""Tests for LGPD compliance features: consent, deletion, and data access."""

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.consent_log import ConsentLog
from app.infrastructure.database.models.user import User
from app.services.auth_service import AuthService
from app.services.lgpd_service import LGPDService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _webhook(phone: str, text: str) -> dict:
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
                                    "id": "wamid.test",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": text},
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
async def named_user(db: AsyncSession):
    """User that already has a real name — bypasses AWAITING_NAME."""
    user = await AuthService.register(
        email="lgpd_test@test.com",
        password="TestPass123!",
        full_name="Maria Silva",
        db=db,
    )
    user.phone = "+5511777000001"
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def consented_user(db: AsyncSession):
    """User that has name and has already given consent."""
    user = await AuthService.register(
        email="lgpd_consented@test.com",
        password="TestPass123!",
        full_name="João Santos",
        db=db,
    )
    user.phone = "+5511777000002"
    db.add(user)
    await db.commit()
    await db.refresh(user)
    # Record consent
    await LGPDService.record_consent(user.id, user.phone, True, db)
    return user


# ── Feature 1: Consent flow ───────────────────────────────────────────────────


async def test_name_registration_leads_to_consent_request(
    client: AsyncClient, db: AsyncSession
):
    """After name is collected, user must accept privacy policy before using the bot."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        # First message creates user, asks for name
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000001", "oi")
        )

        # Second message: user sends name → should receive consent request
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000001", "Ana Paula")
        )

    last_reply = mock_reply.call_args_list[-1][0][1]
    assert (
        "lgpd" in last_reply.lower()
        or "privacidade" in last_reply.lower()
        or "autoriza" in last_reply.lower()
    )
    assert "quingo.com.br" in last_reply.lower()


async def test_consent_yes_welcomes_user(client: AsyncClient, db: AsyncSession):
    """User says SIM → consent recorded, welcome message sent."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000002", "oi")
        )
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000002", "Carlos")
        )
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000002", "sim")
        )

    last_reply = mock_reply.call_args_list[-1][0][1]
    assert (
        "consentimento" in last_reply.lower()
        or "finanças" in last_reply.lower()
        or "obrigado" in last_reply.lower()
    )

    # Check consent was recorded
    result = await db.execute(select(User).where(User.phone == "+5511799000002"))
    user = result.scalar_one()
    consent_result = await db.execute(
        select(ConsentLog).where(ConsentLog.user_id == user.id)
    )
    consent = consent_result.scalar_one_or_none()
    assert consent is not None
    assert consent.consent_given is True


async def test_consent_no_refuses_access(client: AsyncClient, db: AsyncSession):
    """User says NÃO → consent recorded as False, polite refusal sent."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000003", "oi")
        )
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000003", "Fernanda")
        )
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000003", "não")
        )

    last_reply = mock_reply.call_args_list[-1][0][1]
    assert (
        "entendido" in last_reply.lower() or "sem o consentimento" in last_reply.lower()
    )

    result = await db.execute(select(User).where(User.phone == "+5511799000003"))
    user = result.scalar_one()
    consent_result = await db.execute(
        select(ConsentLog).where(ConsentLog.user_id == user.id)
    )
    consent = consent_result.scalar_one_or_none()
    assert consent is not None
    assert consent.consent_given is False


async def test_consent_ambiguous_asks_again(client: AsyncClient, db: AsyncSession):
    """Ambiguous response → bot asks again without recording consent."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000004", "oi")
        )
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000004", "Roberto")
        )
        await client.post(
            "/api/v1/whatsapp/webhook", json=_webhook("+5511799000004", "talvez")
        )

    last_reply = mock_reply.call_args_list[-1][0][1]
    assert "sim" in last_reply.lower() or "não" in last_reply.lower()

    result = await db.execute(select(User).where(User.phone == "+5511799000004"))
    user = result.scalar_one()
    consent_result = await db.execute(
        select(ConsentLog).where(ConsentLog.user_id == user.id)
    )
    consent = consent_result.scalar_one_or_none()
    assert consent is None


# ── Feature 2: LGPDService unit tests ────────────────────────────────────────


async def test_record_consent_creates_log(named_user: User, db: AsyncSession):
    log = await LGPDService.record_consent(named_user.id, named_user.phone, True, db)
    assert log.id is not None
    assert log.user_id == named_user.id
    assert log.consent_given is True
    assert log.consent_version == "1.0"
    assert "quingo.com.br" in log.policy_url


async def test_get_user_data_summary_returns_correct_fields(
    named_user: User, db: AsyncSession
):
    summary = await LGPDService.get_user_data_summary(named_user.id, db)
    assert summary["user"]["full_name"] == "Maria Silva"
    assert summary["user"]["phone"] == "+5511777000001"
    assert "transactions_count" in summary
    assert "consent" in summary


async def test_get_user_data_summary_includes_consent_info(
    consented_user: User, db: AsyncSession
):
    summary = await LGPDService.get_user_data_summary(consented_user.id, db)
    assert summary["consent"]["given"] is True
    assert summary["consent"]["version"] == "1.0"


async def test_format_data_summary_contains_key_fields(
    named_user: User, db: AsyncSession
):
    summary = await LGPDService.get_user_data_summary(named_user.id, db)
    text = LGPDService.format_data_summary(summary)
    assert "Maria Silva" in text
    assert "lgpd" in text.lower() or "LGPD" in text
    assert "quingo.com.br" in text


async def test_export_user_transactions_empty(named_user: User, db: AsyncSession):
    transactions = await LGPDService.export_user_transactions(named_user.id, db)
    assert transactions == []
    text = LGPDService.format_export(transactions)
    assert "ainda não tem" in text.lower()


# ── Feature 3: Right to deletion ─────────────────────────────────────────────


async def test_delete_account_intent_prompts_confirmation(
    client: AsyncClient, named_user: User
):
    """'apagar minha conta' triggers confirmation prompt."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook(named_user.phone, "apagar minha conta"),
        )

    reply = mock_reply.call_args[0][1]
    assert "CONFIRMAR EXCLUSÃO" in reply
    assert "irreversível" in reply.lower() or "permanente" in reply.lower()


async def test_delete_account_wrong_phrase_cancels(
    client: AsyncClient, named_user: User, db: AsyncSession
):
    """Wrong confirmation phrase cancels deletion."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ):
        await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook(named_user.phone, "apagar minha conta"),
        )
        await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook(
                named_user.phone, "confirmar exclusão"
            ),  # wrong case / missing accent
        )

    # User should still exist
    result = await db.execute(select(User).where(User.id == named_user.id))
    user = result.scalar_one_or_none()
    assert user is not None


async def test_delete_account_correct_phrase_removes_user(
    client: AsyncClient, named_user: User, db: AsyncSession
):
    """Exact 'CONFIRMAR EXCLUSÃO' deletes user and all data."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook(named_user.phone, "apagar minha conta"),
        )
        await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook(named_user.phone, "CONFIRMAR EXCLUSÃO"),
        )

    last_reply = mock_reply.call_args_list[-1][0][1]
    assert "excluída" in last_reply.lower() or "removidos" in last_reply.lower()

    # User should be gone
    db.expire_all()
    result = await db.execute(select(User).where(User.id == named_user.id))
    user = result.scalar_one_or_none()
    assert user is None


# ── Feature 4: Right to access ───────────────────────────────────────────────


async def test_my_data_intent_returns_summary(client: AsyncClient, named_user: User):
    """'meus dados' returns a formatted user data summary."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook(named_user.phone, "meus dados"),
        )

    reply = mock_reply.call_args[0][1]
    assert "Maria Silva" in reply
    assert "lgpd" in reply.lower() or "LGPD" in reply


# ── Feature 5: Data portability ───────────────────────────────────────────────


async def test_export_data_intent_returns_transactions(
    client: AsyncClient, named_user: User
):
    """'exportar meus dados' returns formatted transaction list."""
    with patch(
        "app.services.whatsapp_service.WhatsappService._try_send_reply",
        new=AsyncMock(),
    ) as mock_reply:
        await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook(named_user.phone, "exportar meus dados"),
        )

    reply = mock_reply.call_args[0][1]
    assert (
        "transaç" in reply.lower()
        or "exportar" in reply.lower()
        or "ainda não tem" in reply.lower()
    )


# ── LGPDService.delete_user_data ──────────────────────────────────────────────


async def test_lgpd_delete_user_data_removes_user(named_user: User, db: AsyncSession):
    await LGPDService.delete_user_data(named_user.id, db)
    db.expire_all()
    result = await db.execute(select(User).where(User.id == named_user.id))
    assert result.scalar_one_or_none() is None


async def test_lgpd_delete_nonexistent_user_is_noop(db: AsyncSession):
    import uuid

    await LGPDService.delete_user_data(uuid.uuid4(), db)  # should not raise
