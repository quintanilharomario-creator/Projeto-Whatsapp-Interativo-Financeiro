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
from app.services.conversation.financial_intents import (
    FinancialIntent,
    detect_financial_intent,
)
from app.services.conversation.multi_transaction import split_transactions
from app.services.conversation import responses as resp
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

        # ── Financial intents checked first (greetings, balance, goals, etc.) ──
        # Must run before DELETE/EDIT so "remover meta" is handled as GOAL_DELETE
        # rather than a generic DELETE command.
        fin_intent, fin_data = detect_financial_intent(message_text)
        if fin_intent != FinancialIntent.NONE:
            response_text = await WhatsappService._handle_financial_intent(
                fin_intent, fin_data, message_text, user, db
            )
            _QUERY_INTENTS = {
                FinancialIntent.BALANCE,
                FinancialIntent.TEMPORAL_TODAY,
                FinancialIntent.TEMPORAL_YESTERDAY,
                FinancialIntent.TEMPORAL_WEEK,
                FinancialIntent.TEMPORAL_MONTH,
                FinancialIntent.TEMPORAL_LAST_MONTH,
                FinancialIntent.CATEGORY_QUERY,
                FinancialIntent.PLANNING,
                FinancialIntent.INSIGHT,
                FinancialIntent.GOAL_QUERY,
            }
            fin_msg_type = MessageType.QUERY if fin_intent in _QUERY_INTENTS else MessageType.OTHER
            return await WhatsappService._persist_and_reply(
                phone_number,
                user.id,
                message_text,
                fin_msg_type,
                response_text,
                None,
                db,
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

        # ── Multi-transaction check ────────────────────────────────────────
        parts = split_transactions(message_text)
        if parts and len(parts) >= 2:
            response_text = await WhatsappService._handle_multi_transaction(
                parts, user.id, db
            )
            return await WhatsappService._persist_and_reply(
                phone_number,
                user.id,
                message_text,
                MessageType.EXPENSE,
                response_text,
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

    # ── Financial intent dispatcher ───────────────────────────────────────────

    @staticmethod
    async def _handle_financial_intent(
        intent: FinancialIntent,
        data: dict,
        message_text: str,
        user: User,
        db: AsyncSession,
    ) -> str:
        uid = user.id

        if intent == FinancialIntent.GREETING:
            return await WhatsappService._handle_greeting(user, db)

        if intent == FinancialIntent.THANKS:
            return resp.format_thanks(user.full_name)

        if intent == FinancialIntent.GOODBYE:
            return await WhatsappService._handle_goodbye(user, db)

        if intent == FinancialIntent.HELP:
            return resp.format_help()

        if intent == FinancialIntent.BALANCE:
            return await WhatsappService._handle_balance_query(uid, db)

        temporal_map = {
            FinancialIntent.TEMPORAL_TODAY: "today",
            FinancialIntent.TEMPORAL_YESTERDAY: "yesterday",
            FinancialIntent.TEMPORAL_WEEK: "week",
            FinancialIntent.TEMPORAL_MONTH: "month",
            FinancialIntent.TEMPORAL_LAST_MONTH: "last_month",
        }
        if intent in temporal_map:
            return await WhatsappService._handle_temporal_query(
                temporal_map[intent], uid, db
            )

        if intent == FinancialIntent.CATEGORY_QUERY:
            return await WhatsappService._handle_category_query(
                data.get("category", ""), uid, db
            )

        if intent == FinancialIntent.PLANNING:
            return await WhatsappService._handle_planning_query(
                data.get("amount"), uid, db
            )

        if intent == FinancialIntent.INSIGHT:
            return await WhatsappService._handle_insight_request(uid, db)

        if intent == FinancialIntent.GOAL_CREATE:
            return await WhatsappService._handle_goal_create(
                data.get("amount"), uid, db
            )

        if intent == FinancialIntent.GOAL_QUERY:
            return await WhatsappService._handle_goal_query(uid, db)

        if intent == FinancialIntent.GOAL_DELETE:
            return await WhatsappService._handle_goal_delete(uid, db)

        return msg.NOT_UNDERSTOOD

    # ── Greeting / goodbye ────────────────────────────────────────────────────

    @staticmethod
    async def _handle_greeting(user: User, db: AsyncSession) -> str:
        try:
            balance_data = await WhatsappService._get_balance(user.id, db)
            return resp.format_greeting(
                user.full_name, balance_data, datetime.now(timezone.utc)
            )
        except Exception:
            return resp.format_greeting(
                user.full_name, Decimal("0"), datetime.now(timezone.utc)
            )

    @staticmethod
    async def _handle_goodbye(user: User, db: AsyncSession) -> str:
        try:
            balance_data = await WhatsappService._get_balance(user.id, db)
            return resp.format_goodbye(
                user.full_name, balance_data, datetime.now(timezone.utc)
            )
        except Exception:
            return resp.format_goodbye(
                user.full_name, Decimal("0"), datetime.now(timezone.utc)
            )

    # ── Balance query (enhanced) ──────────────────────────────────────────────

    @staticmethod
    async def _handle_balance_query(user_id: uuid.UUID, db: AsyncSession) -> str:
        from app.services.report_service import ReportService

        now = datetime.now(timezone.utc)
        try:
            balance = await ReportService.get_balance(user_id, db)
            monthly = await ReportService.get_monthly_report(
                user_id, now.year, now.month, db
            )
            return resp.format_balance(balance, monthly, now)
        except Exception as e:
            logger.warning("balance_query_failed", error=str(e))
            return "Não consegui buscar seus dados agora. Tente novamente em instantes."

    # ── Temporal queries ──────────────────────────────────────────────────────

    @staticmethod
    async def _handle_temporal_query(
        period: str, user_id: uuid.UUID, db: AsyncSession
    ) -> str:
        from app.services.conversation.temporal_parser import (
            parse_last_month,
            parse_this_month,
            parse_this_week,
            parse_today,
            parse_yesterday,
        )

        parser_map = {
            "today": parse_today,
            "yesterday": parse_yesterday,
            "week": parse_this_week,
            "month": parse_this_month,
            "last_month": parse_last_month,
        }
        start_dt, end_dt, label = parser_map[period]()

        if period == "month":
            # Full monthly summary with category breakdown
            from app.services.report_service import ReportService

            now = datetime.now(timezone.utc)
            try:
                monthly = await ReportService.get_monthly_report(
                    user_id, now.year, now.month, db
                )
                return resp.format_monthly_full(monthly, now)
            except Exception as e:
                logger.warning("monthly_report_failed", error=str(e))
                return "Não consegui buscar o resumo do mês agora."

        if period == "last_month":
            from app.services.report_service import ReportService

            try:
                monthly = await ReportService.get_monthly_report(
                    user_id, start_dt.year, start_dt.month, db
                )
                return resp.format_monthly_full(monthly, start_dt)
            except Exception as e:
                logger.warning("last_month_report_failed", error=str(e))
                return "Não consegui buscar o resumo do mês passado agora."

        transactions = await TransactionService.list_by_user(
            user_id, db, date_from=start_dt, date_to=end_dt
        )
        return resp.format_temporal_summary(
            transactions, label, datetime.now(timezone.utc)
        )

    # ── Category query ────────────────────────────────────────────────────────

    @staticmethod
    async def _handle_category_query(
        category: str, user_id: uuid.UUID, db: AsyncSession
    ) -> str:
        from app.services.report_service import ReportService

        now = datetime.now(timezone.utc)
        try:
            monthly = await ReportService.get_monthly_report(
                user_id, now.year, now.month, db
            )
            total_expense = monthly["total_expense"]

            if not category:
                # "onde gasto mais" → show top categories
                by_cat = monthly.get("by_category", [])
                if not by_cat:
                    return "📊 Nenhuma despesa registrada este mês."
                lines = [f"📊 *Top categorias de {_MONTH_NAMES_PT[now.month]}:*\n"]
                for i, cat in enumerate(by_cat[:5], 1):
                    from app.services.conversation.responses import _cat_emoji

                    emoji = _cat_emoji(cat["category"])
                    pct = int(cat["percentage"])
                    lines.append(
                        f"{emoji} {cat['category']}: {_fmt(cat['total'])} ({pct}%)"
                    )
                return "\n".join(lines)

            # Filter transactions by category (case-insensitive)
            all_txns = await TransactionService.list_by_user(user_id, db)
            from app.infrastructure.database.models.transaction import (
                TransactionType as TT,
            )

            cat_txns = [
                t
                for t in all_txns
                if t.type == TT.EXPENSE and category.lower() in t.category.lower()
            ]
            # Limit to current month
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            cat_txns = [t for t in cat_txns if t.date >= month_start]

            cat_display = category.capitalize() if category else "Categoria"
            return resp.format_category_breakdown(
                cat_display, cat_txns, total_expense, now
            )
        except Exception as e:
            logger.warning("category_query_failed", error=str(e))
            return "Não consegui buscar os dados de categoria agora."

    # ── Planning query ────────────────────────────────────────────────────────

    @staticmethod
    async def _handle_planning_query(
        amount: Decimal | None, user_id: uuid.UUID, db: AsyncSession
    ) -> str:
        now = datetime.now(timezone.utc)
        try:
            balance = await WhatsappService._get_balance(user_id, db)
        except Exception:
            balance = Decimal("0")

        if amount is None:
            import calendar

            last_day = calendar.monthrange(now.year, now.month)[1]
            days_left = max(0, last_day - now.day)
            daily = balance / days_left if days_left > 0 else balance
            return (
                f"💡 *Quanto você pode gastar?*\n\n"
                f"💰 Saldo atual: *{_fmt(balance)}*\n"
                f"📅 Faltam {days_left} dia(s) até fim do mês\n"
                f"💡 Daria *{_fmt(daily)}/dia* restantes"
            )

        if amount <= balance:
            return resp.format_planning_can(amount, balance, now)
        return resp.format_planning_cannot(amount, balance)

    # ── Insight request ───────────────────────────────────────────────────────

    @staticmethod
    async def _handle_insight_request(user_id: uuid.UUID, db: AsyncSession) -> str:
        try:
            from app.services.ai_service import AIService
            from app.services.report_service import ReportService

            now = datetime.now(timezone.utc)
            monthly = await ReportService.get_monthly_report(
                user_id, now.year, now.month, db
            )
            summary = await ReportService.get_summary(user_id, db)
            context = (
                f"Gastos do mês: {monthly['total_expense']}\n"
                f"Receitas: {monthly['total_income']}\n"
                f"Por categoria: {monthly.get('by_category', [])}\n"
                f"Últimas transações: {summary.get('recent_transactions', [])}"
            )
            result = await AIService().answer_question(
                question="Analise meus gastos e dê 2-3 dicas práticas para economizar. "
                "Seja específico com os valores reais. Resposta curta, em português, com emojis.",
                context=context,
                user_id=str(user_id),
            )
            return f"💡 *Análise dos seus gastos*\n\n{result}"
        except Exception as e:
            logger.warning("insight_request_failed", error=str(e))
            return (
                "💡 *Dicas para economizar:*\n\n"
                "1️⃣ Registre todos os gastos diariamente\n"
                "2️⃣ Crie uma meta de economia mensal\n"
                "3️⃣ Revise as categorias onde mais gasta\n\n"
                "Para análise personalizada, diga 'resumo do mês' primeiro! 📊"
            )

    # ── Goal handlers ─────────────────────────────────────────────────────────

    @staticmethod
    async def _handle_goal_create(
        amount: Decimal | None, user_id: uuid.UUID, db: AsyncSession
    ) -> str:
        from app.services.goals import GoalService

        if not amount or amount <= 0:
            return (
                "🎯 Qual valor você quer economizar?\n\n"
                "Exemplo: _'quero economizar 1000 esse mês'_"
            )

        goal = await GoalService.create(user_id, amount, db)
        progress = await GoalService.calculate_progress(user_id, db)
        saved = progress.get("saved", Decimal("0"))
        return resp.format_goal_created(amount, saved, goal.period_end)

    @staticmethod
    async def _handle_goal_query(user_id: uuid.UUID, db: AsyncSession) -> str:
        from app.services.goals import GoalService

        progress = await GoalService.calculate_progress(user_id, db)
        if not progress:
            return resp.format_no_goal()

        return resp.format_goal_progress(
            progress["target"],
            progress["saved"],
            progress["period_end"],
        )

    @staticmethod
    async def _handle_goal_delete(user_id: uuid.UUID, db: AsyncSession) -> str:
        from app.services.goals import GoalService

        deleted = await GoalService.deactivate(user_id, db)
        if deleted:
            return resp.format_goal_deleted()
        return resp.format_goal_not_found()

    # ── Multi-transaction handler ─────────────────────────────────────────────

    @staticmethod
    async def _handle_multi_transaction(
        parts: list[str], user_id: uuid.UUID, db: AsyncSession
    ) -> str:
        results: list[tuple[str, Decimal, str]] = []

        for part in parts:
            try:
                parsed = WhatsappParser.parse(part)
                if (
                    parsed.message_type not in (MessageType.INCOME, MessageType.EXPENSE)
                    or not parsed.amount
                ):
                    continue
                txn = await WhatsappService._do_create_transaction(
                    parsed, user_id, part, db
                )
                type_label = (
                    "receita"
                    if parsed.message_type == MessageType.INCOME
                    else "despesa"
                )
                cat_display = (
                    f"{parsed.category} › {parsed.subcategory}"
                    if parsed.subcategory
                    else (parsed.category or "Outros")
                )
                results.append((type_label, txn.amount, cat_display))
            except Exception as e:
                logger.warning("multi_transaction_part_failed", part=part, error=str(e))

        if not results:
            return msg.NOT_UNDERSTOOD

        balance = await WhatsappService._get_balance(user_id, db)
        return resp.format_multi_transactions(results, balance)

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
