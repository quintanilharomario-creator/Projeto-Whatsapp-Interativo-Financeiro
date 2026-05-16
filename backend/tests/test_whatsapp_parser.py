from decimal import Decimal

from app.infrastructure.database.models.whatsapp_message import MessageType
from app.services.whatsapp_parser import WhatsappParser


def test_parse_expense_with_amount():
    result = WhatsappParser.parse("Gastei R$50 no mercado")
    assert result.message_type == MessageType.EXPENSE
    assert result.amount == Decimal("50")
    assert result.category == "Alimentação"
    assert result.confidence >= 0.8


def test_parse_expense_comma_decimal():
    result = WhatsappParser.parse("Paguei 80,50 de conta de luz")
    assert result.message_type == MessageType.EXPENSE
    assert result.amount == Decimal("80.50")
    assert result.category == "Moradia"


def test_parse_income():
    result = WhatsappParser.parse("Recebi R$ 1.500,00 de salário")
    assert result.message_type == MessageType.INCOME
    assert result.amount == Decimal("1500.00")
    assert result.category == "Renda"
    assert result.confidence >= 0.8


def test_parse_query():
    result = WhatsappParser.parse("Qual é meu saldo?")
    assert result.message_type == MessageType.QUERY
    assert result.amount is None
    assert result.confidence >= 0.8


def test_parse_other():
    result = WhatsappParser.parse("Olá, tudo bem?")
    assert result.message_type == MessageType.OTHER
    assert result.amount is None


def test_parse_expense_no_amount():
    result = WhatsappParser.parse("Gastei no restaurante")
    assert result.message_type == MessageType.EXPENSE
    assert result.amount is None
    assert result.confidence < 0.8


def test_parse_transport_category():
    result = WhatsappParser.parse("Paguei R$25 de Uber")
    assert result.message_type == MessageType.EXPENSE
    assert result.category == "Transporte"


def test_parse_health_category():
    result = WhatsappParser.parse("Comprei remédio na farmácia por R$40")
    assert result.message_type == MessageType.EXPENSE
    assert result.category == "Saúde"


def test_parse_entertainment_category():
    result = WhatsappParser.parse("Paguei R$30 do Netflix")
    assert result.message_type == MessageType.EXPENSE
    assert result.category == "Lazer"


def test_parse_amount_without_currency_symbol():
    result = WhatsappParser.parse("Gastei 100 no supermercado")
    assert result.amount == Decimal("100")


def test_parse_query_extrato():
    result = WhatsappParser.parse("Me manda meu extrato do mês")
    assert result.message_type == MessageType.QUERY


def test_parse_income_pix():
    result = WhatsappParser.parse("Pix recebido de R$500")
    assert result.message_type == MessageType.INCOME
    assert result.amount == Decimal("500")


def test_parse_income_servico_category():
    result = WhatsappParser.parse("recebi 1000 de serviço")
    assert result.message_type == MessageType.INCOME
    assert result.category == "Renda"


def test_parse_income_freelance_category():
    result = WhatsappParser.parse("recebi 500 de freelance")
    assert result.message_type == MessageType.INCOME
    assert result.category == "Renda"


def test_parse_income_consultoria_category():
    result = WhatsappParser.parse("ganhei 2000 de consultoria")
    assert result.message_type == MessageType.INCOME
    assert result.category == "Renda"


def test_parse_query_balanco():
    result = WhatsappParser.parse("me mostra o balanço")
    assert result.message_type == MessageType.QUERY


def test_parse_query_movimentacoes():
    result = WhatsappParser.parse("quero ver minhas movimentações")
    assert result.message_type == MessageType.QUERY


def test_infer_income_from_category_only():
    """'500 holerite' has no income verb — type should be inferred from category."""
    result = WhatsappParser.parse("500 holerite")
    assert result.message_type == MessageType.INCOME
    assert result.amount == Decimal("500")
    assert result.confidence >= 0.5


def test_infer_expense_from_category_only():
    """'30 uber' has no expense verb — type should be inferred from category."""
    result = WhatsappParser.parse("30 uber")
    assert result.message_type == MessageType.EXPENSE
    assert result.amount == Decimal("30")
    assert result.confidence >= 0.5


def test_formal_income_verb_receita():
    result = WhatsappParser.parse("receita de 1000 em freelance")
    assert result.message_type == MessageType.INCOME


def test_formal_income_verb_entrada():
    result = WhatsappParser.parse("entrada de 500 hoje")
    assert result.message_type == MessageType.INCOME


def test_formal_income_verb_credito():
    result = WhatsappParser.parse("crédito de 2000 na conta")
    assert result.message_type == MessageType.INCOME


def test_formal_expense_verb_despesa():
    result = WhatsappParser.parse("despesa de 300 com aluguel")
    assert result.message_type == MessageType.EXPENSE


def test_formal_expense_verb_pagamento():
    result = WhatsappParser.parse("pagamento de 150 feito")
    assert result.message_type == MessageType.EXPENSE
