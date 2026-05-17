"""Tests for user name registration on first WhatsApp interaction."""

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.conversation_state import ConversationState
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.whatsapp_message import MessageType
from app.services.whatsapp_service import WhatsappService

_NEW_PHONE = "+5521900000001"
_OLD_PHONE = "+5521900000002"


@pytest_asyncio.fixture
async def existing_user_without_name(db: AsyncSession) -> User:
    """Simulates a legacy user auto-created with placeholder name."""
    user = User(
        phone=_OLD_PHONE,
        full_name="WhatsApp 0002",
        email=f"{_OLD_PHONE}@hermes.local",
        hashed_password="whatsapp_auto_created",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── 1. New user is asked for their name ──────────────────────────────────────


async def test_new_user_asked_for_name(db: AsyncSession):
    msg = await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    assert msg.transaction_id is None
    assert "bem-vindo" in (msg.response_text or "").lower()
    assert "hermes" in (msg.response_text or "").lower()
    assert "nome" in (msg.response_text or "").lower()


# ── 2. Name registration succeeds ────────────────────────────────────────────


async def test_name_registration_success(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    msg = await WhatsappService.receive_message(_NEW_PHONE, "Romario", db)

    assert "Romario" in (msg.response_text or "")
    assert "prazer" in (msg.response_text or "").lower()
    # After name collection, user sees LGPD consent request
    assert (
        "autoriza" in (msg.response_text or "").lower()
        or "privacidade" in (msg.response_text or "").lower()
    )


# ── 3. Name too short is rejected ────────────────────────────────────────────


async def test_name_too_short_rejected(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    msg = await WhatsappService.receive_message(_NEW_PHONE, "a", db)

    assert "nome" in (msg.response_text or "").lower()
    # State still active — user can try again
    result = await db.execute(
        select(ConversationState).where(ConversationState.user_id == msg.user_id)
    )
    state = result.scalar_one_or_none()
    assert state is not None
    assert state.current_intent == "AWAITING_NAME"


# ── 4. Name is capitalized correctly ─────────────────────────────────────────


async def test_name_capitalized_correctly(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    msg = await WhatsappService.receive_message(_NEW_PHONE, "romario quintanilha", db)

    assert "Romario Quintanilha" in (msg.response_text or "")


# ── 5. Name is saved to the database ─────────────────────────────────────────


async def test_name_saved_to_database(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)
    await WhatsappService.receive_message(_NEW_PHONE, "Romario", db)

    result = await db.execute(select(User).where(User.phone == _NEW_PHONE))
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.full_name == "Romario"


# ── 6. Welcome message uses name in subsequent interaction ───────────────────


async def test_welcome_message_after_name(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    msg = await WhatsappService.receive_message(_NEW_PHONE, "Aline", db)

    assert "Aline" in (msg.response_text or "")
    assert msg.message_type == MessageType.OTHER


# ── 7. Existing user without real name is asked ──────────────────────────────


async def test_existing_user_without_name_asked(
    db: AsyncSession, existing_user_without_name: User
):
    msg = await WhatsappService.receive_message(_OLD_PHONE, "qual meu saldo?", db)

    assert "nome" in (msg.response_text or "").lower()
    assert msg.transaction_id is None


# ── 8. Name is used in subsequent responses after registration ───────────────


async def test_name_used_in_subsequent_responses(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)
    await WhatsappService.receive_message(_NEW_PHONE, "Carlos", db)
    # Accept LGPD consent so state is cleared and bot can respond normally
    await WhatsappService.receive_message(_NEW_PHONE, "sim", db)

    msg = await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    assert "Carlos" in (msg.response_text or "")


# ── 9. Accented names are handled correctly ───────────────────────────────────


async def test_special_chars_in_name_handled(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    msg = await WhatsappService.receive_message(_NEW_PHONE, "josé da silva", db)

    assert "José Da Silva" in (msg.response_text or "")
    result = await db.execute(select(User).where(User.phone == _NEW_PHONE))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.full_name == "José Da Silva"


# ── 10. Very long name is truncated to 50 characters ────────────────────────


async def test_very_long_name_truncated(db: AsyncSession):
    await WhatsappService.receive_message(_NEW_PHONE, "oi", db)

    long_name = "Abcdefghij " * 6  # 66 chars
    msg = await WhatsappService.receive_message(_NEW_PHONE, long_name, db)

    result = await db.execute(select(User).where(User.phone == _NEW_PHONE))
    user = result.scalar_one_or_none()
    assert user is not None
    assert len(user.full_name) <= 50
    assert "prazer" in (msg.response_text or "").lower()
