import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserNotFoundError
from app.infrastructure.database.models.transaction import Transaction
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.whatsapp_message import MessageType, WhatsappMessage
from app.services.auth_service import AuthService
from app.services.transaction_service import TransactionService
from app.services.whatsapp_parser import WhatsappParser


class WhatsappService:
    @staticmethod
    async def get_or_create_user(phone_number: str, db: AsyncSession) -> User | None:
        result = await db.execute(select(User).where(User.phone == phone_number))
        user = result.scalar_one_or_none()
        return user

    @staticmethod
    async def receive_message(
        phone_number: str,
        message_text: str,
        db: AsyncSession,
    ) -> WhatsappMessage:
        user = await WhatsappService.get_or_create_user(phone_number, db)
        parsed = WhatsappParser.parse(message_text)

        transaction_id: uuid.UUID | None = None

        if (
            user
            and parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE)
            and parsed.amount
            and parsed.confidence >= 0.5
        ):
            from app.infrastructure.database.models.transaction import TransactionType

            txn_type = (
                TransactionType.INCOME
                if parsed.message_type == MessageType.INCOME
                else TransactionType.EXPENSE
            )
            txn = await TransactionService.create(
                user_id=user.id,
                type=txn_type,
                amount=parsed.amount,
                description=message_text[:200],
                category=parsed.category or "Outros",
                date=datetime.now(timezone.utc),
                db=db,
            )
            transaction_id = txn.id

        response_text = WhatsappService._build_response(parsed, transaction_id)

        msg = WhatsappMessage(
            user_id=user.id if user else None,
            phone_number=phone_number,
            message_text=message_text,
            message_type=parsed.message_type,
            extracted_amount=parsed.amount,
            category=parsed.category,
            confidence=parsed.confidence,
            response_text=response_text,
            transaction_id=transaction_id,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    def _build_response(parsed, transaction_id) -> str:
        if parsed.message_type == MessageType.QUERY:
            return "Para ver seu saldo e extrato, acesse o app ou envie 'extrato'."

        if parsed.message_type == MessageType.OTHER:
            return (
                "Não entendi. Envie algo como: 'Gastei R$50 no mercado' "
                "ou 'Recebi R$1000 de salário'."
            )

        if not transaction_id:
            if not parsed.amount:
                return "Qual foi o valor?"
            return (
                "Você não está cadastrado. Crie sua conta no app para "
                "registrar transações pelo WhatsApp."
            )

        type_label = "receita" if parsed.message_type == MessageType.INCOME else "gasto"
        return (
            f"✓ {type_label.capitalize()} de R$ {parsed.amount:.2f} "
            f"em {parsed.category} registrado!"
        )

    @staticmethod
    async def list_messages(
        phone_number: str,
        db: AsyncSession,
        limit: int = 20,
    ) -> list[WhatsappMessage]:
        result = await db.execute(
            select(WhatsappMessage)
            .where(WhatsappMessage.phone_number == phone_number)
            .order_by(WhatsappMessage.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
