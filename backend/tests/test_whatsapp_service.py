from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.whatsapp_message import (
    MessageType,
    WhatsappMessage,
)
from app.services.auth_service import AuthService
from app.services.whatsapp_service import WhatsappService


@pytest_asyncio.fixture
async def user_with_phone(db: AsyncSession):
    user = await AuthService.register(
        email="whatsapp@test.com",
        password="TestPass123!",
        full_name="WA User",
        db=db,
    )
    user.phone = "+5511999999999"
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_receive_expense_message_creates_transaction(
    db: AsyncSession, user_with_phone
):
    msg = await WhatsappService.receive_message(
        phone_number="+5511999999999",
        message_text="Gastei R$50 no mercado",
        db=db,
    )
    assert msg.message_type == MessageType.EXPENSE
    assert msg.extracted_amount == Decimal("50")
    assert msg.transaction_id is not None
    assert msg.response_text is not None
    assert "50" in msg.response_text


async def test_receive_income_message_creates_transaction(
    db: AsyncSession, user_with_phone
):
    msg = await WhatsappService.receive_message(
        phone_number="+5511999999999",
        message_text="Recebi R$1000 de salário",
        db=db,
    )
    assert msg.message_type == MessageType.INCOME
    assert msg.extracted_amount == Decimal("1000")
    assert msg.transaction_id is not None


async def test_receive_query_message_no_transaction(db: AsyncSession, user_with_phone):
    msg = await WhatsappService.receive_message(
        phone_number="+5511999999999",
        message_text="Qual é meu saldo?",
        db=db,
    )
    assert msg.message_type == MessageType.QUERY
    assert msg.transaction_id is None
    assert msg.response_text is not None
    assert "R$" in (msg.response_text or "")


async def test_query_saldo_shows_balance(db: AsyncSession, user_with_phone):
    await WhatsappService.receive_message(
        "+5511999999999", "Recebi R$1000 de salário", db
    )
    msg = await WhatsappService.receive_message(
        phone_number="+5511999999999",
        message_text="qual meu saldo",
        db=db,
    )
    assert "saldo" in (msg.response_text or "").lower()
    assert "R$ 1.000,00" in (msg.response_text or "")


async def test_query_extrato_shows_transactions(db: AsyncSession, user_with_phone):
    await WhatsappService.receive_message(
        "+5511999999999", "Gastei R$50 no mercado", db
    )
    msg = await WhatsappService.receive_message(
        phone_number="+5511999999999",
        message_text="extrato",
        db=db,
    )
    assert msg.message_type == MessageType.QUERY
    assert "Extrato" in (msg.response_text or "")
    assert "R$" in (msg.response_text or "")


async def test_auto_create_user_on_first_message(db: AsyncSession):
    msg = await WhatsappService.receive_message(
        phone_number="+5500000000000",
        message_text="Gastei R$30 no restaurante",
        db=db,
    )
    assert msg.user_id is not None
    assert msg.transaction_id is not None
    assert "hermes" in (msg.response_text or "").lower()
    assert "bem-vindo" in (msg.response_text or "").lower()
    assert "transação foi registrada" in (msg.response_text or "").lower()


async def test_receive_other_message(db: AsyncSession, user_with_phone):
    msg = await WhatsappService.receive_message(
        phone_number="+5511999999999",
        message_text="Olá, tudo bem?",
        db=db,
    )
    assert msg.message_type == MessageType.OTHER
    assert msg.transaction_id is None


async def test_list_messages(db: AsyncSession, user_with_phone):
    await WhatsappService.receive_message("+5511999999999", "Gastei R$10 no café", db)
    await WhatsappService.receive_message("+5511999999999", "Gastei R$20 no almoço", db)

    messages = await WhatsappService.list_messages("+5511999999999", db)
    assert len(messages) == 2


async def test_list_messages_empty(db: AsyncSession):
    messages = await WhatsappService.list_messages("+5599999999999", db)
    assert messages == []


async def test_message_stored_in_db(db: AsyncSession, user_with_phone):
    await WhatsappService.receive_message(
        "+5511999999999", "Paguei R$100 de internet", db
    )

    result = await db.execute(
        select(WhatsappMessage).where(WhatsappMessage.phone_number == "+5511999999999")
    )
    msgs = result.scalars().all()
    assert len(msgs) == 1
    assert msgs[0].extracted_amount == Decimal("100")
