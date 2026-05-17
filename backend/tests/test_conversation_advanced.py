"""Advanced conversational feature tests — balance, temporal, categories, planning,
greetings, multi-transactions, goals."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.transaction import TransactionType
from app.services.conversation.financial_intents import (
    FinancialIntent,
    detect_financial_intent,
)
from app.services.conversation.multi_transaction import split_transactions
from app.services.conversation.temporal_parser import (
    parse_last_month,
    parse_this_month,
    parse_this_week,
    parse_today,
    parse_yesterday,
)
from app.services.goals import GoalService
from app.services.transaction_service import TransactionService
from app.services.whatsapp_service import WhatsappService

PHONE = "+5511999990099"


@pytest_asyncio.fixture
async def user(db: AsyncSession):
    u, _ = await WhatsappService.get_or_create_user(PHONE, db)
    # Set a real name so the name-registration flow doesn't intercept test messages
    u.full_name = "Test User"
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def transactions(user, db: AsyncSession):
    """Create a realistic set of transactions for the current month."""
    now = datetime.now(timezone.utc)
    txns = [
        ("EXPENSE", Decimal("800.00"), "Moradia", "aluguel"),
        ("EXPENSE", Decimal("400.00"), "Alimentação", "mercado"),
        ("EXPENSE", Decimal("150.00"), "Alimentação", "restaurante"),
        ("EXPENSE", Decimal("100.00"), "Transporte", "uber"),
        ("INCOME", Decimal("5000.00"), "Renda", "salário"),
    ]
    created = []
    for type_str, amount, category, description in txns:
        txn = await TransactionService.create(
            user_id=user.id,
            type=TransactionType.INCOME
            if type_str == "INCOME"
            else TransactionType.EXPENSE,
            amount=amount,
            description=description,
            category=category,
            date=now,
            db=db,
        )
        created.append(txn)
    return created


# ─────────────────────────────────────────────────────────────────────────────
# Financial Intent Detection (unit tests — no DB needed)
# ─────────────────────────────────────────────────────────────────────────────


class TestFinancialIntentDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "saldo",
            "qual meu saldo",
            "meu saldo",
            "saldo atual",
            "quanto tenho",
            "quanto eu tenho",
            "to com quanto",
            "dinheiro",
            "situação",
            "como estou",
            "sobrou quanto",
            "no vermelho",
        ],
    )
    def test_balance_intent_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.BALANCE

    @pytest.mark.parametrize(
        "text",
        [
            "bom dia",
            "boa tarde",
            "boa noite",
            "oi",
            "olá",
            "tudo bem",
            "como vai",
        ],
    )
    def test_greeting_intent_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.GREETING

    @pytest.mark.parametrize("text", ["obrigado", "obg", "valeu", "vlw"])
    def test_thanks_intent_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.THANKS

    @pytest.mark.parametrize("text", ["tchau", "até", "ate logo", "flw", "falou"])
    def test_goodbye_intent_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.GOODBYE

    @pytest.mark.parametrize("text", ["ajuda", "help", "menu", "comandos", "?"])
    def test_help_intent_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.HELP

    @pytest.mark.parametrize(
        "text",
        [
            "quanto gastei hoje",
            "gastos de hoje",
            "o que gastei hoje",
        ],
    )
    def test_temporal_today_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.TEMPORAL_TODAY

    def test_temporal_yesterday_detection(self):
        intent, _ = detect_financial_intent("quanto gastei ontem")
        assert intent == FinancialIntent.TEMPORAL_YESTERDAY

    @pytest.mark.parametrize("text", ["essa semana", "gastos da semana", "essa semana"])
    def test_temporal_week_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.TEMPORAL_WEEK

    @pytest.mark.parametrize(
        "text",
        ["resumo do mês", "esse mês", "extrato do mês", "quanto gastei esse mês"],
    )
    def test_temporal_month_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.TEMPORAL_MONTH

    @pytest.mark.parametrize("text", ["mês passado", "mês anterior"])
    def test_temporal_last_month_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.TEMPORAL_LAST_MONTH

    @pytest.mark.parametrize(
        "text",
        [
            "quanto gastei com alimentação",
            "gastos com transporte",
            "onde gasto mais",
            "maior despesa",
        ],
    )
    def test_category_query_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.CATEGORY_QUERY

    def test_category_query_extracts_name(self):
        _, data = detect_financial_intent("quanto gastei com alimentação")
        assert "alimenta" in data.get("category", "").lower()

    @pytest.mark.parametrize(
        "text",
        [
            "posso gastar 500?",
            "consigo comprar algo por 200?",
            "quanto posso gastar hoje?",
        ],
    )
    def test_planning_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.PLANNING

    def test_planning_extracts_amount(self):
        _, data = detect_financial_intent("posso gastar 500?")
        assert data.get("amount") == Decimal("500")

    @pytest.mark.parametrize(
        "text",
        [
            "me ajuda a economizar",
            "como posso poupar",
            "alguma dica",
            "dica financeira",
        ],
    )
    def test_insight_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.INSIGHT

    @pytest.mark.parametrize(
        "text",
        [
            "quero economizar 1000",
            "criar meta de 500",
            "quero poupar 2000",
        ],
    )
    def test_goal_create_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.GOAL_CREATE

    def test_goal_create_extracts_amount(self):
        _, data = detect_financial_intent("quero economizar 1000 esse mês")
        assert data.get("amount") == Decimal("1000")

    @pytest.mark.parametrize("text", ["minha meta", "como estou na meta", "meta atual"])
    def test_goal_query_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.GOAL_QUERY

    @pytest.mark.parametrize("text", ["remover meta", "cancelar meta", "excluir meta"])
    def test_goal_delete_detection(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.GOAL_DELETE

    @pytest.mark.parametrize(
        "text",
        [
            "gastei 50 no mercado",
            "recebi 1000 de salário",
            "paguei 100 de luz",
        ],
    )
    def test_transaction_returns_none_intent(self, text):
        intent, _ = detect_financial_intent(text)
        assert intent == FinancialIntent.NONE


# ─────────────────────────────────────────────────────────────────────────────
# Temporal Parser (unit tests — no DB)
# ─────────────────────────────────────────────────────────────────────────────


class TestTemporalParser:
    def test_today_range_is_same_day(self):
        start, end, label = parse_today()
        assert start.date() == end.date()
        assert "Hoje" in label

    def test_yesterday_range_is_previous_day(self):
        start, end, label = parse_yesterday()
        today = datetime.now(timezone.utc).date()
        assert start.date() == today - __import__("datetime").timedelta(days=1)
        assert "Ontem" in label

    def test_week_starts_on_monday(self):
        start, end, label = parse_this_week()
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6  # Sunday
        assert "semana" in label.lower()

    def test_month_starts_on_day_1(self):
        start, end, label = parse_this_month()
        assert start.day == 1
        assert start.hour == 0
        now = datetime.now(timezone.utc)
        assert str(now.year) in label

    def test_last_month_correct_bounds(self):
        start, end, label = parse_last_month()
        assert start.day == 1
        assert end.day >= 28  # last day of month
        assert start.month != datetime.now(timezone.utc).month


# ─────────────────────────────────────────────────────────────────────────────
# Multi-transaction Parser (unit tests — no DB)
# ─────────────────────────────────────────────────────────────────────────────


class TestMultiTransactionParser:
    def test_two_transactions_with_e(self):
        result = split_transactions("gastei 50 no mercado e 30 no uber")
        assert result is not None
        assert len(result) == 2
        assert "50" in result[0]
        assert "30" in result[1]

    def test_three_transactions_with_comma_and_e(self):
        result = split_transactions("comprei 100 de roupa, 50 de café e 200 de mercado")
        assert result is not None
        assert len(result) == 3

    def test_single_transaction_returns_none(self):
        result = split_transactions("gastei 50 no mercado")
        assert result is None

    def test_verb_propagated_to_second_segment(self):
        result = split_transactions("gastei 50 no mercado e 30 no uber")
        assert result is not None
        # Second segment should have a verb (gastei or similar)
        assert any(
            v in result[1].lower() for v in ["gastei", "gast", "comprei", "pagu"]
        )

    def test_text_without_amounts_returns_none(self):
        result = split_transactions("bom dia, como vai")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — balance and greetings
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_balance_query_returns_summary(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "qual meu saldo", db)
    assert msg.response_text is not None
    assert "saldo" in msg.response_text.lower() or "R$" in msg.response_text


@pytest.mark.asyncio
async def test_balance_keyword_saldo(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "saldo", db)
    assert "R$" in msg.response_text


@pytest.mark.asyncio
async def test_balance_shows_income_and_expense(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "quanto tenho", db)
    # Should show both income and expense
    text = msg.response_text
    assert "5.000" in text or "5000" in text  # income amount


@pytest.mark.asyncio
async def test_greeting_bom_dia(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "bom dia", db)
    assert msg.response_text is not None
    # Should contain saldo
    assert "R$" in msg.response_text or "saldo" in msg.response_text.lower()


@pytest.mark.asyncio
async def test_greeting_oi(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "oi", db)
    assert msg.response_text is not None
    assert len(msg.response_text) > 10


@pytest.mark.asyncio
async def test_thanks_response(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "obrigado", db)
    assert (
        "nada" in msg.response_text.lower() or "precisar" in msg.response_text.lower()
    )


@pytest.mark.asyncio
async def test_thanks_valeu(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "valeu", db)
    assert msg.response_text is not None
    assert len(msg.response_text) > 5


@pytest.mark.asyncio
async def test_goodbye_tchau(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "tchau", db)
    assert "logo" in msg.response_text.lower() or "R$" in msg.response_text


@pytest.mark.asyncio
async def test_help_menu_contains_key_sections(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "ajuda", db)
    text = msg.response_text
    assert "REGISTROS" in text or "registr" in text.lower()
    assert "CONSULTAS" in text or "saldo" in text.lower()


@pytest.mark.asyncio
async def test_help_menu_command(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "menu", db)
    assert (
        "gastei" in msg.response_text.lower() or "recebi" in msg.response_text.lower()
    )


@pytest.mark.asyncio
async def test_help_question_mark(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "?", db)
    assert msg.response_text is not None
    assert len(msg.response_text) > 20


# ─────────────────────────────────────────────────────────────────────────────
# Temporal queries
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_temporal_today_returns_summary(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "quanto gastei hoje", db)
    assert msg.response_text is not None
    assert "Hoje" in msg.response_text or "hoje" in msg.response_text.lower()


@pytest.mark.asyncio
async def test_temporal_today_no_transactions(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "quanto gastei hoje", db)
    # Should return a message (even if no expenses)
    assert msg.response_text is not None
    assert len(msg.response_text) > 5


@pytest.mark.asyncio
async def test_temporal_week_query(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "gastos dessa semana", db)
    assert msg.response_text is not None
    assert "semana" in msg.response_text.lower()


@pytest.mark.asyncio
async def test_temporal_month_returns_full_summary(
    user, transactions, db: AsyncSession
):
    msg = await WhatsappService.receive_message(PHONE, "resumo do mês", db)
    text = msg.response_text
    # Should have income and expense
    assert "Receitas" in text or "receita" in text.lower()
    assert "Despesas" in text or "despesa" in text.lower()


@pytest.mark.asyncio
async def test_temporal_month_shows_categories(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "como foi meu mês", db)
    # Should list top categories
    text = msg.response_text
    assert "Alimentação" in text or "alimentação" in text.lower() or "R$" in text


@pytest.mark.asyncio
async def test_temporal_last_month_query(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "mês passado", db)
    assert msg.response_text is not None
    assert len(msg.response_text) > 5


@pytest.mark.asyncio
async def test_temporal_yesterday_query(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "quanto gastei ontem", db)
    assert "Ontem" in msg.response_text or "ontem" in msg.response_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Category queries
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_category_query_alimentacao(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(
        PHONE, "quanto gastei com alimentação", db
    )
    text = msg.response_text
    assert "alimenta" in text.lower() or "R$" in text


@pytest.mark.asyncio
async def test_category_query_no_results(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "gastos com saúde", db)
    # Should return a graceful "no results" message
    assert msg.response_text is not None
    assert len(msg.response_text) > 5


@pytest.mark.asyncio
async def test_category_query_where_spend_most(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "onde gasto mais", db)
    assert msg.response_text is not None
    # Should contain at least one category
    assert "R$" in msg.response_text or "categoria" in msg.response_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Planning queries
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_planning_can_spend(user, transactions, db: AsyncSession):
    # With R$ 3550 balance (5000 - 1450), can spend R$ 100
    msg = await WhatsappService.receive_message(PHONE, "posso gastar 100?", db)
    text = msg.response_text
    assert "100" in text
    # Should be affirmative
    assert "pode" in text.lower() or "disponível" in text.lower() or "TEM" in text


@pytest.mark.asyncio
async def test_planning_cannot_spend(user, transactions, db: AsyncSession):
    # With R$ 3550 balance, cannot spend R$ 9999
    msg = await WhatsappService.receive_message(PHONE, "posso gastar 9999?", db)
    text = msg.response_text
    assert "9.999" in text or "9999" in text
    # Should be warning
    assert "Atenção" in text or "maior" in text.lower() or "aten" in text.lower()


@pytest.mark.asyncio
async def test_planning_no_amount_shows_daily_budget(
    user, transactions, db: AsyncSession
):
    msg = await WhatsappService.receive_message(PHONE, "quanto posso gastar hoje?", db)
    assert msg.response_text is not None
    assert "R$" in msg.response_text


# ─────────────────────────────────────────────────────────────────────────────
# Multiple transactions
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multi_transaction_two_items(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(
        PHONE, "gastei 50 no mercado e 30 no uber", db
    )
    text = msg.response_text
    assert "50" in text
    assert "30" in text
    # Should show registered count or saldo
    assert "registrada" in text.lower() or "R$" in text


@pytest.mark.asyncio
async def test_multi_transaction_three_items(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(
        PHONE, "comprei 100 de roupa, 50 de café e 200 de mercado", db
    )
    text = msg.response_text
    assert "100" in text
    assert "50" in text
    assert "200" in text


@pytest.mark.asyncio
async def test_multi_transaction_updates_balance(user, db: AsyncSession):
    # Add income first
    await TransactionService.create(
        user_id=user.id,
        type=TransactionType.INCOME,
        amount=Decimal("1000.00"),
        description="renda",
        category="Renda",
        date=datetime.now(timezone.utc),
        db=db,
    )
    msg = await WhatsappService.receive_message(
        PHONE, "gastei 50 no mercado e 30 no uber", db
    )
    # Balance should be mentioned
    assert "R$" in msg.response_text


# ─────────────────────────────────────────────────────────────────────────────
# Goal management
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_goal_create(user, transactions, db: AsyncSession):
    msg = await WhatsappService.receive_message(
        PHONE, "quero economizar 1000 esse mês", db
    )
    text = msg.response_text
    assert "meta" in text.lower() or "1.000" in text or "1000" in text


@pytest.mark.asyncio
async def test_goal_query_after_create(user, transactions, db: AsyncSession):
    # Create goal first
    await GoalService.create(user.id, Decimal("1000.00"), db)
    msg = await WhatsappService.receive_message(PHONE, "minha meta", db)
    text = msg.response_text
    assert "1.000" in text or "meta" in text.lower()


@pytest.mark.asyncio
async def test_goal_progress_shows_percentage(user, transactions, db: AsyncSession):
    await GoalService.create(user.id, Decimal("2000.00"), db)
    msg = await WhatsappService.receive_message(PHONE, "como estou na meta", db)
    text = msg.response_text
    assert "%" in text or "meta" in text.lower()


@pytest.mark.asyncio
async def test_goal_query_without_goal(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "minha meta", db)
    text = msg.response_text
    # Should show friendly "no goal" message
    assert "meta" in text.lower()


@pytest.mark.asyncio
async def test_goal_delete(user, db: AsyncSession):
    await GoalService.create(user.id, Decimal("500.00"), db)
    msg = await WhatsappService.receive_message(PHONE, "remover meta", db)
    text = msg.response_text
    assert "removida" in text.lower() or "meta" in text.lower()


@pytest.mark.asyncio
async def test_goal_delete_when_no_goal(user, db: AsyncSession):
    msg = await WhatsappService.receive_message(PHONE, "cancelar meta", db)
    assert msg.response_text is not None
    assert "meta" in msg.response_text.lower()


@pytest.mark.asyncio
async def test_goal_second_replaces_first(user, db: AsyncSession):
    await GoalService.create(user.id, Decimal("500.00"), db)
    await GoalService.create(user.id, Decimal("1000.00"), db)
    # Only one active goal should exist
    goal = await GoalService.get_active(user.id, db)
    assert goal is not None
    assert Decimal(str(goal.target_amount)) == Decimal("1000.00")


# ─────────────────────────────────────────────────────────────────────────────
# GoalService unit tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_goal_service_create_and_get(user, db: AsyncSession):
    goal = await GoalService.create(user.id, Decimal("1500.00"), db)
    assert goal.is_active is True
    assert Decimal(str(goal.target_amount)) == Decimal("1500.00")

    fetched = await GoalService.get_active(user.id, db)
    assert fetched is not None
    assert fetched.id == goal.id


@pytest.mark.asyncio
async def test_goal_service_deactivate(user, db: AsyncSession):
    await GoalService.create(user.id, Decimal("800.00"), db)
    result = await GoalService.deactivate(user.id, db)
    assert result is True
    fetched = await GoalService.get_active(user.id, db)
    assert fetched is None


@pytest.mark.asyncio
async def test_goal_service_deactivate_when_none(user, db: AsyncSession):
    result = await GoalService.deactivate(user.id, db)
    assert result is False


@pytest.mark.asyncio
async def test_goal_service_calculate_progress_no_goal(user, db: AsyncSession):
    progress = await GoalService.calculate_progress(user.id, db)
    assert progress == {}


@pytest.mark.asyncio
async def test_goal_service_calculate_progress_with_transactions(
    user, transactions, db: AsyncSession
):
    # transactions fixture: 5000 income - 1450 expenses = 3550 saved
    await GoalService.create(user.id, Decimal("2000.00"), db)
    progress = await GoalService.calculate_progress(user.id, db)
    assert "target" in progress
    assert "saved" in progress
    assert "pct" in progress
    assert progress["pct"] >= 0
    assert progress["pct"] <= 100
