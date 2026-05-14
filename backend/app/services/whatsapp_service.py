import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserNotFoundError
from app.core.logging import get_logger
from app.infrastructure.database.models.transaction import Transaction, TransactionType
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.whatsapp_message import MessageType, WhatsappMessage
from app.services.auth_service import AuthService
from app.services.transaction_service import TransactionService
from app.services.whatsapp_parser import ParsedMessage, WhatsappParser

logger = get_logger(__name__)


class WhatsappService:
    @staticmethod
    async def get_or_create_user(phone_number: str, db: AsyncSession) -> User | None:
        result = await db.execute(select(User).where(User.phone == phone_number))
        return result.scalar_one_or_none()

    @staticmethod
    async def receive_message(
        phone_number: str,
        message_text: str,
        db: AsyncSession,
    ) -> WhatsappMessage:
        user = await WhatsappService.get_or_create_user(phone_number, db)
        parsed = WhatsappParser.parse(message_text)

        # AI enhancement: try to improve classification when regex confidence is low
        if parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE):
            parsed = await WhatsappService._try_ai_classify(
                message_text, parsed, user_id=str(user.id) if user else None
            )

        transaction_id: uuid.UUID | None = None

        if (
            user
            and parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE)
            and parsed.amount
            and parsed.confidence >= 0.5
        ):
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

        # AI enhancement: improve WhatsApp response if user exists
        if user and transaction_id:
            response_text = await WhatsappService._try_enhance_response(
                response_text, str(user.id), db
            )

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
    async def _try_ai_classify(
        text: str,
        fallback: ParsedMessage,
        user_id: str | None,
    ) -> ParsedMessage:
        try:
            from app.services.ai_service import AIService
            suggestion = await AIService().analyze_transaction(text, user_id=user_id)
            if suggestion.confidence > 0.8:
                msg_type = (
                    MessageType.INCOME
                    if suggestion.type == TransactionType.INCOME
                    else MessageType.EXPENSE
                )
                return ParsedMessage(
                    message_type=msg_type,
                    amount=suggestion.amount if suggestion.amount is not None else fallback.amount,
                    category=suggestion.category,
                    confidence=suggestion.confidence,
                )
        except Exception as e:
            logger.debug("ai_classify_fallback", reason=str(e))
        return fallback

    @staticmethod
    async def _try_enhance_response(
        response_text: str,
        user_id: str,
        db: AsyncSession,
    ) -> str:
        try:
            from app.services.ai_service import AIService
            return await AIService().enhance_whatsapp_response(response_text, user_id, db)
        except Exception as e:
            logger.debug("ai_enhance_fallback", reason=str(e))
            return response_text

    @staticmethod
    def _build_response(parsed: ParsedMessage, transaction_id: uuid.UUID | None) -> str:
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
