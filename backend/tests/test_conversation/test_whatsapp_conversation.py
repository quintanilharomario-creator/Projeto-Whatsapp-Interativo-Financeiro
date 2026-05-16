"""Integration tests for the WhatsApp conversational flow."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.transaction import TransactionType
from app.services.conversation.messages import (
    NOTHING_CHANGED,
    NO_ACTIVE_STATE,
    NO_TRANSACTION_TO_ACT_ON,
)
from app.services.conversation.state_manager import StateManager
from app.services.transaction_service import TransactionService
from app.services.whatsapp_service import WhatsappService


PHONE = "+5511999990001"


@pytest_asyncio.fixture
async def user(db: AsyncSession):
    user, _ = await WhatsappService.get_or_create_user(PHONE, db)
    return user


@pytest_asyncio.fixture
async def expense_txn(user, db: AsyncSession):
    return await TransactionService.create(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("50.00"),
        description="mercado",
        category="Alimentação",
        date=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        db=db,
    )


# ── Delete flow ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_intent_creates_state(user, expense_txn, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "apaga essa despesa", db)
    assert "Confirma" in msg.response_text
    assert "50" in msg.response_text
    state = await StateManager.get(user.id, db)
    assert state is not None
    assert state.current_intent == "AWAITING_DELETE_CONFIRM"


@pytest.mark.asyncio
async def test_delete_confirm_yes_deletes(user, expense_txn, db: AsyncSession):
    # Trigger delete intent
    await WhatsappService.receive_message(PHONE, "apaga o último gasto", db)
    # Confirm
    msg = await WhatsappService.receive_message(PHONE, "sim", db)
    assert "apagada" in msg.response_text.lower()
    assert "saldo" in msg.response_text.lower()
    # Transaction should be gone
    latest = await TransactionService.get_latest(user.id, db)
    assert latest is None


@pytest.mark.asyncio
async def test_delete_confirm_no_keeps_transaction(user, expense_txn, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "apaga o último", db)
    msg = await WhatsappService.receive_message(PHONE, "não", db)
    assert NOTHING_CHANGED in msg.response_text
    # Transaction still exists
    still_there = await TransactionService.get_latest(user.id, db)
    assert still_there is not None
    assert still_there.id == expense_txn.id


@pytest.mark.asyncio
async def test_delete_no_transaction_friendly_message(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "apaga essa despesa", db)
    assert NO_TRANSACTION_TO_ACT_ON in msg.response_text


@pytest.mark.asyncio
async def test_delete_state_clears_after_confirm(user, expense_txn, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "apaga o último", db)
    await WhatsappService.receive_message(PHONE, "sim", db)
    state = await StateManager.get(user.id, db)
    assert state is None


# ── Edit flow ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_intent_creates_state(user, expense_txn, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "era 100, não 50", db)
    assert "Confirma" in msg.response_text
    assert "100" in msg.response_text
    state = await StateManager.get(user.id, db)
    assert state is not None
    assert state.current_intent == "AWAITING_EDIT_CONFIRM"


@pytest.mark.asyncio
async def test_edit_confirm_yes_updates_amount(user, expense_txn, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "era 100, não 50", db)
    msg = await WhatsappService.receive_message(PHONE, "sim", db)
    assert "atualizada" in msg.response_text.lower() or "100" in msg.response_text
    updated = await TransactionService.get_latest(user.id, db)
    assert updated.amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_edit_confirm_no_keeps_original(user, expense_txn, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "era 100, não 50", db)
    msg = await WhatsappService.receive_message(PHONE, "não", db)
    assert NOTHING_CHANGED in msg.response_text
    txn = await TransactionService.get_latest(user.id, db)
    assert txn.amount == Decimal("50.00")


@pytest.mark.asyncio
async def test_edit_de_para_syntax(user, expense_txn, db: AsyncSession):
    msg = await WhatsappService.receive_message(
        PHONE, "edita o valor de 50 para 75", db
    )
    assert "75" in msg.response_text
    assert "Confirma" in msg.response_text


@pytest.mark.asyncio
async def test_edit_no_transaction(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "era 100, não 50", db)
    assert NO_TRANSACTION_TO_ACT_ON in msg.response_text


# ── Category selection flow ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ambiguous_expense_triggers_menu(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "paguei 100", db)
    assert "categoria" in msg.response_text.lower() or "1️⃣" in msg.response_text
    state = await StateManager.get(user.id, db)
    assert state is not None
    assert state.current_intent == "AWAITING_CATEGORY"


@pytest.mark.asyncio
async def test_category_selection_by_number(user, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "paguei 100", db)
    msg = await WhatsappService.receive_message(PHONE, "1", db)
    assert "Alimentação" in msg.response_text
    assert "registrada" in msg.response_text.lower()
    latest = await TransactionService.get_latest(user.id, db)
    assert latest is not None
    assert latest.amount == Decimal("100.00")
    assert latest.category == "Alimentação"


@pytest.mark.asyncio
async def test_category_selection_by_name(user, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "paguei 100", db)
    msg = await WhatsappService.receive_message(PHONE, "transporte", db)
    assert "Transporte" in msg.response_text
    latest = await TransactionService.get_latest(user.id, db)
    assert latest.category == "Transporte"


@pytest.mark.asyncio
async def test_income_without_category_triggers_menu(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "recebi 500", db)
    assert "fonte" in msg.response_text.lower() or "1️⃣" in msg.response_text
    state = await StateManager.get(user.id, db)
    assert state.pending_data["transaction_type"] == "INCOME"


@pytest.mark.asyncio
async def test_income_category_selection(user, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "recebi 500", db)
    msg = await WhatsappService.receive_message(PHONE, "2", db)
    assert "Freelance" in msg.response_text
    latest = await TransactionService.get_latest(user.id, db)
    assert latest.type == TransactionType.INCOME


@pytest.mark.asyncio
async def test_category_deny_aborts(user, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "paguei 100", db)
    msg = await WhatsappService.receive_message(PHONE, "não", db)
    assert NOTHING_CHANGED in msg.response_text
    assert await TransactionService.get_latest(user.id, db) is None


@pytest.mark.asyncio
async def test_invalid_category_choice_stays_in_state(user, db: AsyncSession):
    await WhatsappService.receive_message(PHONE, "paguei 100", db)
    msg = await WhatsappService.receive_message(PHONE, "xyz_unknown_cat", db)
    assert (
        "opção" in msg.response_text.lower() or "reconheci" in msg.response_text.lower()
    )
    # State should still be active
    state = await StateManager.get(user.id, db)
    assert state is not None


# ── Friendly not-understood ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_not_understood_shows_help(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "bla bla bla", db)
    assert (
        "não consegui entender" in msg.response_text.lower()
        or "📝" in msg.response_text
    )


@pytest.mark.asyncio
async def test_lone_number_without_state_shows_no_context(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "2", db)
    assert msg.response_text == NO_ACTIVE_STATE


@pytest.mark.asyncio
async def test_lone_confirm_without_state(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "sim", db)
    assert msg.response_text == NO_ACTIVE_STATE


# ── State expiry ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expired_state_is_ignored(user, expense_txn, db: AsyncSession):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    from app.infrastructure.database.models.conversation_state import ConversationState

    # Create a state and immediately expire it
    await StateManager.set(
        user.id,
        "AWAITING_DELETE_CONFIRM",
        {
            "transaction_id": str(expense_txn.id),
            "amount": "50.00",
            "category": "Alimentação",
            "type_label": "despesa",
        },
        db,
    )
    await db.execute(
        update(ConversationState)
        .where(ConversationState.user_id == user.id)
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await db.commit()

    # "sim" should NOT delete the transaction (state is expired)
    msg = await WhatsappService.receive_message(PHONE, "sim", db)
    assert msg.response_text == NO_ACTIVE_STATE
    txn = await TransactionService.get_latest(user.id, db)
    assert txn is not None
