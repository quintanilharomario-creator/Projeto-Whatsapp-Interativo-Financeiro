import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.database.models.transaction import TransactionType
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.whatsapp_message import (
    MessageType,
    WhatsappMessage,
)
from app.services.transaction_service import TransactionService
from app.services.whatsapp_parser import ParsedMessage, WhatsappParser

logger = get_logger(__name__)


class WhatsappService:
    @staticmethod
    async def get_or_create_user(
        phone_number: str, db: AsyncSession
    ) -> tuple[User, bool]:
        """Returns (user, is_new). Creates user automatically if not found."""
        result = await db.execute(select(User).where(User.phone == phone_number))
        user = result.scalar_one_or_none()

        if user:
            return user, False

        user = User(
            phone=phone_number,
            full_name=f"WhatsApp {phone_number[-4:]}",
            email=f"{phone_number}@hermes.local",
            hashed_password="whatsapp_auto_created",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(
            "whatsapp_user_auto_created",
            phone=phone_number,
            user_id=str(user.id),
        )

        return user, True

    @staticmethod
    async def receive_message(
        phone_number: str,
        message_text: str,
        db: AsyncSession,
    ) -> WhatsappMessage:
        user, is_new = await WhatsappService.get_or_create_user(phone_number, db)
        parsed = WhatsappParser.parse(message_text)

        # AI enhancement: try to improve classification when regex confidence is low
        if parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE):
            parsed = await WhatsappService._try_ai_classify(
                message_text, parsed, user_id=str(user.id)
            )

        transaction_id: uuid.UUID | None = None

        if (
            parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE)
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

        if is_new:
            response_text = WhatsappService._build_welcome_message(
                phone_number, transaction_id
            )
        else:
            response_text = WhatsappService._build_response(parsed, transaction_id)
            # AI enhancement: improve WhatsApp response when transaction was created
            if transaction_id:
                response_text = await WhatsappService._try_enhance_response(
                    response_text, str(user.id), db
                )

        # User just sent a message → always within 24h window
        await WhatsappService._try_send_reply(
            phone_number, response_text, within_window=True
        )

        msg = WhatsappMessage(
            user_id=user.id,
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
    def _build_welcome_message(
        phone_number: str,
        transaction_id: uuid.UUID | None,
    ) -> str:
        txn_line = "\n\nSua transação foi registrada! 🎉" if transaction_id else ""
        return (
            f"👋 Olá! Bem-vindo ao Hermes!\n\n"
            f"Sou seu assistente financeiro pessoal.\n\n"
            f"✅ Sua conta foi criada automaticamente\n"
            f"📱 Vinculada a: {phone_number}\n\n"
            f"Você pode:\n"
            f"💰 Registrar receitas: 'recebi 1000 de salário'\n"
            f"💸 Registrar despesas: 'gastei 50 no mercado'\n"
            f"📊 Ver saldo: 'qual meu saldo?'\n"
            f"🎤 Mandar áudio com qualquer comando"
            f"{txn_line}"
        )

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
                    amount=suggestion.amount
                    if suggestion.amount is not None
                    else fallback.amount,
                    category=suggestion.category,
                    confidence=suggestion.confidence,
                )
        except Exception as e:
            logger.debug("ai_classify_fallback", reason=str(e))
        return fallback

    @staticmethod
    async def _is_within_24h_window(phone_number: str, db: AsyncSession) -> bool:
        """Returns True if this phone sent a message in the last 24 hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(WhatsappMessage)
            .where(
                WhatsappMessage.phone_number == phone_number,
                WhatsappMessage.created_at >= cutoff,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def transcribe_and_process(
        phone_number: str,
        audio_bytes: bytes,
        db: AsyncSession,
    ) -> WhatsappMessage:
        """Transcribe audio via Whisper and process as a regular message.

        Falls back to a stored error record (with a friendly reply) if
        the API key is missing or transcription fails for any reason.
        """
        from app.core.config import settings
        from app.core.exceptions import AIServiceError
        from app.infrastructure.audio.whisper_provider import WhisperProvider

        _FALLBACK = (
            "Desculpe, não consegui entender o áudio. "
            "Por favor, envie uma mensagem de texto."
        )

        if not settings.OPENAI_API_KEY:
            logger.warning("audio_no_openai_key", phone=phone_number)
            await WhatsappService._try_send_reply(phone_number, _FALLBACK)
            msg = WhatsappMessage(
                phone_number=phone_number,
                message_text="[áudio — OPENAI_API_KEY não configurada]",
                message_type=MessageType.OTHER,
                response_text=_FALLBACK,
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            return msg

        try:
            text = await WhisperProvider().transcribe(audio_bytes, filename="audio.ogg")
            logger.info("audio_transcribed", phone=phone_number, preview=text[:50])
        except (AIServiceError, Exception) as exc:
            logger.warning(
                "audio_transcription_failed", phone=phone_number, error=str(exc)
            )
            await WhatsappService._try_send_reply(phone_number, _FALLBACK)
            msg = WhatsappMessage(
                phone_number=phone_number,
                message_text="[áudio — transcrição falhou]",
                message_type=MessageType.OTHER,
                response_text=_FALLBACK,
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            return msg

        return await WhatsappService.receive_message(
            phone_number=phone_number,
            message_text=text,
            db=db,
        )

    @staticmethod
    async def _try_send_reply(
        phone_number: str,
        response_text: str,
        within_window: bool = True,
    ) -> None:
        from app.core.config import settings

        try:
            if settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
                from app.infrastructure.whatsapp.cloud_api_provider import (
                    CloudAPIProvider,
                )

                await CloudAPIProvider().send_message(
                    phone=phone_number,
                    message=response_text,
                    within_window=within_window,
                )
        except Exception as e:
            logger.warning("whatsapp_reply_failed", phone=phone_number, error=str(e))

    @staticmethod
    async def _try_enhance_response(
        response_text: str,
        user_id: str,
        db: AsyncSession,
    ) -> str:
        try:
            from app.services.ai_service import AIService

            return await AIService().enhance_whatsapp_response(
                response_text, user_id, db
            )
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
            return "Não consegui processar sua mensagem. Tente reformular."

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
