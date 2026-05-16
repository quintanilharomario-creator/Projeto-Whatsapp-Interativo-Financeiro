import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.database.models.conversation_state import ConversationState
from app.infrastructure.database.models.transaction import TransactionType
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.whatsapp_message import (
    MessageType,
    WhatsappMessage,
)
from app.services.conversation import ConvIntent, StateManager, detect
from app.services.conversation.intent_detector import extract_edit_amounts
from app.services.conversation import messages as msg
from app.services.conversation.suggestion_engine import (
    expense_menu,
    income_menu,
    resolve_choice,
)
from app.services.transaction_service import TransactionService
from app.services.whatsapp_parser import ParsedMessage, WhatsappParser

logger = get_logger(__name__)

_MONTH_NAMES_PT = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]

# ── Intents stored in ConversationState.current_intent ───────────────────────
_AWAIT_DELETE = "AWAITING_DELETE_CONFIRM"
_AWAIT_EDIT = "AWAITING_EDIT_CONFIRM"
_AWAIT_CATEGORY = "AWAITING_CATEGORY"


class WhatsappService:
    # ── Public entry-point ────────────────────────────────────────────────────

    @staticmethod
    async def get_or_create_user(
        phone_number: str, db: AsyncSession
    ) -> tuple[User, bool]:
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
            "whatsapp_user_auto_created", phone=phone_number, user_id=str(user.id)
        )
        return user, True

    @staticmethod
    async def receive_message(
        phone_number: str,
        message_text: str,
        db: AsyncSession,
    ) -> WhatsappMessage:
        user, is_new = await WhatsappService.get_or_create_user(phone_number, db)

        # ── New-user welcome (possibly with first transaction) ─────────────
        if is_new:
            parsed = WhatsappParser.parse(message_text)
            transaction_id: uuid.UUID | None = None
            if (
                parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE)
                and parsed.amount
                and parsed.confidence >= 0.5
                and (parsed.category or "Outros") != "Outros"
            ):
                txn = await WhatsappService._do_create_transaction(
                    parsed, user.id, message_text, db
                )
                transaction_id = txn.id

            response_text = WhatsappService._build_welcome_message(
                phone_number, transaction_id
            )
            return await WhatsappService._persist_and_reply(
                phone_number,
                user.id,
                message_text,
                MessageType.OTHER,
                response_text,
                transaction_id,
                db,
            )

        # ── Active conversation state → route to state handler ────────────
        state = await StateManager.get(user.id, db)
        if state:
            response_text, msg_type, txn_id = await WhatsappService._dispatch_state(
                state, message_text, user.id, db
            )
            return await WhatsappService._persist_and_reply(
                phone_number, user.id, message_text, msg_type, response_text, txn_id, db
            )

        # ── Detect meta-intents (DELETE / EDIT) ────────────────────────────
        conv_intent, menu_number = detect(message_text)

        if conv_intent == ConvIntent.DELETE:
            response_text = await WhatsappService._handle_delete_intent(user.id, db)
            return await WhatsappService._persist_and_reply(
                phone_number,
                user.id,
                message_text,
                MessageType.OTHER,
                response_text,
                None,
                db,
            )

        if conv_intent == ConvIntent.EDIT:
            response_text = await WhatsappService._handle_edit_intent(
                message_text, user.id, db
            )
            return await WhatsappService._persist_and_reply(
                phone_number,
                user.id,
                message_text,
                MessageType.OTHER,
                response_text,
                None,
                db,
            )

        if conv_intent in (ConvIntent.CONFIRM, ConvIntent.DENY, ConvIntent.NUMBER):
            return await WhatsappService._persist_and_reply(
                phone_number,
                user.id,
                message_text,
                MessageType.OTHER,
                msg.NO_ACTIVE_STATE,
                None,
                db,
            )

        # ── Normal message parsing ─────────────────────────────────────────
        parsed = WhatsappParser.parse(message_text)
        if parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE):
            parsed = await WhatsappService._try_ai_classify(
                message_text, parsed, user_id=str(user.id)
            )

        response_text, msg_type, txn_id = await WhatsappService._handle_parsed(
            parsed, message_text, user.id, db
        )

        if txn_id:
            response_text = await WhatsappService._try_enhance_response(
                response_text, str(user.id), db
            )

        return await WhatsappService._persist_and_reply(
            phone_number,
            user.id,
            message_text,
            msg_type,
            response_text,
            txn_id,
            db,
            parsed=parsed,
        )

    # ── Normal message handler ────────────────────────────────────────────────

    @staticmethod
    async def _handle_parsed(
        parsed: ParsedMessage,
        message_text: str,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> tuple[str, MessageType, uuid.UUID | None]:
        if parsed.message_type == MessageType.QUERY:
            text = await WhatsappService._handle_query(message_text, user_id, db)
            return text, MessageType.QUERY, None

        if parsed.message_type in (MessageType.INCOME, MessageType.EXPENSE):
            if not parsed.amount:
                return msg.ASK_AMOUNT, MessageType.OTHER, None

            # Category unclear → show menu, hold transaction in state
            if (parsed.category or "Outros") == "Outros":
                if parsed.message_type == MessageType.INCOME:
                    menu_text, options = income_menu(parsed.amount)
                else:
                    menu_text, options = expense_menu(parsed.amount)

                await StateManager.set(
                    user_id,
                    _AWAIT_CATEGORY,
                    {
                        "transaction_type": parsed.message_type.value,
                        "amount": str(parsed.amount),
                        "description": message_text[:200],
                        "options": [[m, s] for m, s in options],
                    },
                    db,
                )
                return menu_text, MessageType.OTHER, None

            # Create transaction
            txn = await WhatsappService._do_create_transaction(
                parsed, user_id, message_text, db
            )
            balance = await WhatsappService._get_balance(user_id, db)
            type_label = (
                "receita" if parsed.message_type == MessageType.INCOME else "despesa"
            )
            cat_display = (
                f"{parsed.category} › {parsed.subcategory}"
                if parsed.subcategory
                else (parsed.category or "Outros")
            )
            return (
                msg.transaction_registered(
                    type_label, parsed.amount, cat_display, balance
                ),
                parsed.message_type,
                txn.id,
            )

        # OTHER
        return msg.NOT_UNDERSTOOD, MessageType.OTHER, None

    # ── Conversation state dispatcher ─────────────────────────────────────────

    @staticmethod
    async def _dispatch_state(
        state: ConversationState,
        message_text: str,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> tuple[str, MessageType, uuid.UUID | None]:
        intent = state.current_intent
        data = state.pending_data
        conv_intent, menu_number = detect(message_text)

        if intent == _AWAIT_DELETE:
            return await WhatsappService._handle_delete_confirm(
                conv_intent, data, user_id, db
            )

        if intent == _AWAIT_EDIT:
            return await WhatsappService._handle_edit_confirm(
                conv_intent, data, user_id, db
            )

        if intent == _AWAIT_CATEGORY:
            return await WhatsappService._handle_category_response(
                conv_intent, menu_number, message_text, data, user_id, db
            )

        # Unknown state — clear it and let user start fresh
        await StateManager.clear(user_id, db)
        return msg.NOT_UNDERSTOOD, MessageType.OTHER, None

    # ── Delete flow ───────────────────────────────────────────────────────────

    @staticmethod
    async def _handle_delete_intent(user_id: uuid.UUID, db: AsyncSession) -> str:
        latest = await TransactionService.get_latest(user_id, db)
        if not latest:
            return msg.NO_TRANSACTION_TO_ACT_ON

        type_label = "receita" if latest.type == TransactionType.INCOME else "despesa"
        await StateManager.set(
            user_id,
            _AWAIT_DELETE,
            {
                "transaction_id": str(latest.id),
                "amount": str(latest.amount),
                "category": latest.category,
                "type_label": type_label,
            },
            db,
        )
        return msg.delete_confirm(type_label, latest.amount, latest.category)

    @staticmethod
    async def _handle_delete_confirm(
        conv_intent: ConvIntent,
        data: dict,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> tuple[str, MessageType, uuid.UUID | None]:
        await StateManager.clear(user_id, db)

        if conv_intent not in (ConvIntent.CONFIRM,):
            return msg.NOTHING_CHANGED, MessageType.OTHER, None

        txn_id = uuid.UUID(data["transaction_id"])
        await TransactionService.delete(txn_id, user_id, db)

        balance = await WhatsappService._get_balance(user_id, db)
        return (
            msg.delete_success(data["type_label"], balance),
            MessageType.OTHER,
            None,
        )

    # ── Edit flow ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _handle_edit_intent(
        message_text: str, user_id: uuid.UUID, db: AsyncSession
    ) -> str:
        latest = await TransactionService.get_latest(user_id, db)
        if not latest:
            return msg.NO_TRANSACTION_TO_ACT_ON

        new_amount_f, _old_hint = extract_edit_amounts(message_text)
        if not new_amount_f or new_amount_f <= 0:
            return (
                f"Encontrei sua última transação: {_fmt(latest.amount)} "
                f"em {latest.category}.\n\n"
                "Para qual valor você quer corrigir?"
            )

        new_amount = Decimal(str(round(new_amount_f, 2)))
        await StateManager.set(
            user_id,
            _AWAIT_EDIT,
            {
                "transaction_id": str(latest.id),
                "old_amount": str(latest.amount),
                "new_amount": str(new_amount),
            },
            db,
        )
        return msg.edit_confirm(latest.amount, new_amount)

    @staticmethod
    async def _handle_edit_confirm(
        conv_intent: ConvIntent,
        data: dict,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> tuple[str, MessageType, uuid.UUID | None]:
        await StateManager.clear(user_id, db)

        if conv_intent not in (ConvIntent.CONFIRM,):
            return msg.NOTHING_CHANGED, MessageType.OTHER, None

        txn_id = uuid.UUID(data["transaction_id"])
        new_amount = Decimal(data["new_amount"])
        await TransactionService.update(txn_id, user_id, db, amount=new_amount)

        balance = await WhatsappService._get_balance(user_id, db)
        return (
            msg.edit_success(new_amount, balance),
            MessageType.OTHER,
            None,
        )

    # ── Category selection flow ───────────────────────────────────────────────

    @staticmethod
    async def _handle_category_response(
        conv_intent: ConvIntent,
        menu_number: int | None,
        message_text: str,
        data: dict,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> tuple[str, MessageType, uuid.UUID | None]:
        # Deny → abort
        if conv_intent == ConvIntent.DENY:
            await StateManager.clear(user_id, db)
            return msg.NOTHING_CHANGED, MessageType.OTHER, None

        options = [tuple(pair) for pair in data["options"]]

        # Resolve: number takes priority, then full text
        if conv_intent == ConvIntent.NUMBER and menu_number is not None:
            choice: int | str = menu_number
        else:
            choice = message_text.strip()

        resolved = resolve_choice(choice, options)
        if not resolved:
            return msg.INVALID_CHOICE, MessageType.OTHER, None

        main_cat, sub_cat = resolved
        amount = Decimal(data["amount"])
        txn_type = (
            TransactionType.INCOME
            if data["transaction_type"] == "INCOME"
            else TransactionType.EXPENSE
        )
        msg_type = (
            MessageType.INCOME
            if txn_type == TransactionType.INCOME
            else MessageType.EXPENSE
        )

        txn = await TransactionService.create(
            user_id=user_id,
            type=txn_type,
            amount=amount,
            description=data.get("description", "")[:200],
            category=main_cat,
            date=datetime.now(timezone.utc),
            db=db,
        )
        await StateManager.clear(user_id, db)

        balance = await WhatsappService._get_balance(user_id, db)
        type_label = "receita" if txn_type == TransactionType.INCOME else "despesa"
        cat_display = f"{main_cat} › {sub_cat}" if sub_cat else main_cat
        return (
            msg.transaction_registered(type_label, amount, cat_display, balance),
            msg_type,
            txn.id,
        )

    # ── Query handler ─────────────────────────────────────────────────────────

    @staticmethod
    async def _handle_query(
        message_text: str, user_id: uuid.UUID, db: AsyncSession
    ) -> str:
        from app.services.report_service import ReportService

        text = message_text.lower()
        is_extract = any(kw in text for kw in ("extrato", "movimenta", "transa"))
        now = datetime.now(timezone.utc)

        try:
            monthly = await ReportService.get_monthly_report(
                user_id, now.year, now.month, db
            )
            if is_extract:
                summary = await ReportService.get_summary(user_id, db)
                return WhatsappService._format_extract_response(monthly, summary, now)
            else:
                balance = await ReportService.get_balance(user_id, db)
                return WhatsappService._format_balance_response(balance, monthly, now)
        except Exception as e:
            logger.warning("query_report_failed", error=str(e))
            return "Não consegui buscar seus dados agora. Tente novamente em instantes."

    # ── AI helpers ────────────────────────────────────────────────────────────

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

    # ── WhatsApp send ─────────────────────────────────────────────────────────

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

    # ── Persistence helper ────────────────────────────────────────────────────

    @staticmethod
    async def _persist_and_reply(
        phone_number: str,
        user_id: uuid.UUID,
        message_text: str,
        msg_type: MessageType,
        response_text: str,
        transaction_id: uuid.UUID | None,
        db: AsyncSession,
        parsed: "ParsedMessage | None" = None,
    ) -> WhatsappMessage:
        await WhatsappService._try_send_reply(
            phone_number, response_text, within_window=True
        )
        whatsapp_msg = WhatsappMessage(
            user_id=user_id,
            phone_number=phone_number,
            message_text=message_text,
            message_type=msg_type,
            response_text=response_text,
            transaction_id=transaction_id,
            extracted_amount=parsed.amount if parsed else None,
            category=parsed.category if parsed else None,
            confidence=parsed.confidence if parsed else None,
        )
        db.add(whatsapp_msg)
        await db.commit()
        await db.refresh(whatsapp_msg)
        return whatsapp_msg

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    async def _do_create_transaction(
        parsed: ParsedMessage,
        user_id: uuid.UUID,
        message_text: str,
        db: AsyncSession,
    ):
        txn_type = (
            TransactionType.INCOME
            if parsed.message_type == MessageType.INCOME
            else TransactionType.EXPENSE
        )
        return await TransactionService.create(
            user_id=user_id,
            type=txn_type,
            amount=parsed.amount,  # type: ignore[arg-type]
            description=message_text[:200],
            category=parsed.category or "Outros",
            date=datetime.now(timezone.utc),
            db=db,
        )

    @staticmethod
    async def _get_balance(user_id: uuid.UUID, db: AsyncSession) -> Decimal:
        from app.services.report_service import ReportService

        try:
            data = await ReportService.get_balance(user_id, db)
            return data["balance"]
        except Exception:
            return Decimal("0.00")

    @staticmethod
    def _fmt_brl(value: Decimal) -> str:
        formatted = f"{value:,.2f}"
        return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _build_welcome_message(
        phone_number: str, transaction_id: uuid.UUID | None
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
    def _format_balance_response(balance: dict, monthly: dict, now: datetime) -> str:
        month_name = _MONTH_NAMES_PT[now.month]
        fmt = WhatsappService._fmt_brl
        return (
            f"💰 Seu saldo atual: {fmt(balance['balance'])}\n\n"
            f"📊 Este mês ({month_name}/{now.year}):\n"
            f"✅ Receitas: {fmt(monthly['total_income'])}\n"
            f"❌ Despesas: {fmt(monthly['total_expense'])}"
        )

    @staticmethod
    def _format_extract_response(monthly: dict, summary: dict, now: datetime) -> str:
        month_name = _MONTH_NAMES_PT[now.month]
        fmt = WhatsappService._fmt_brl
        lines = [
            f"📋 Extrato de {month_name}/{now.year}:\n",
            f"💰 Receitas: {fmt(monthly['total_income'])}",
            f"❌ Despesas: {fmt(monthly['total_expense'])}",
            f"📊 Saldo: {fmt(monthly['balance'])}",
        ]
        recent = summary.get("recent_transactions", [])
        if recent:
            lines.append("\nÚltimas transações:")
            for txn in recent[:5]:
                date_str = txn["date"][:10]
                day_month = f"{date_str[8:10]}/{date_str[5:7]}"
                icon = "✅" if txn["type"] == "INCOME" else "💸"
                amount = fmt(Decimal(str(txn["amount"])))
                cat = txn.get("category") or "Outros"
                lines.append(f"{icon} {day_month} - {amount} - {cat}")
        return "\n".join(lines)

    # ── Audio transcription ───────────────────────────────────────────────────

    @staticmethod
    async def transcribe_and_process(
        phone_number: str,
        audio_bytes: bytes,
        db: AsyncSession,
    ) -> WhatsappMessage:
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
            whatsapp_msg = WhatsappMessage(
                phone_number=phone_number,
                message_text="[áudio — OPENAI_API_KEY não configurada]",
                message_type=MessageType.OTHER,
                response_text=_FALLBACK,
            )
            db.add(whatsapp_msg)
            await db.commit()
            await db.refresh(whatsapp_msg)
            return whatsapp_msg

        try:
            text = await WhisperProvider().transcribe(audio_bytes, filename="audio.ogg")
            logger.info("audio_transcribed", phone=phone_number, preview=text[:50])
        except (AIServiceError, Exception) as exc:
            logger.warning(
                "audio_transcription_failed", phone=phone_number, error=str(exc)
            )
            await WhatsappService._try_send_reply(phone_number, _FALLBACK)
            whatsapp_msg = WhatsappMessage(
                phone_number=phone_number,
                message_text="[áudio — transcrição falhou]",
                message_type=MessageType.OTHER,
                response_text=_FALLBACK,
            )
            db.add(whatsapp_msg)
            await db.commit()
            await db.refresh(whatsapp_msg)
            return whatsapp_msg

        return await WhatsappService.receive_message(
            phone_number=phone_number,
            message_text=text,
            db=db,
        )

    @staticmethod
    async def _is_within_24h_window(phone_number: str, db: AsyncSession) -> bool:
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


def _fmt(amount: Decimal) -> str:
    formatted = f"{amount:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")
