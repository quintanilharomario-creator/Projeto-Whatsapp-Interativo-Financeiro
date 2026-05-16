"""Unit tests for the category suggestion engine."""

from decimal import Decimal


from app.services.conversation.suggestion_engine import (
    expense_menu,
    income_menu,
    resolve_choice,
)


def test_expense_menu_contains_amount():
    text, options = expense_menu(Decimal("50.00"))
    assert "50" in text
    assert len(options) == 5


def test_income_menu_contains_amount():
    text, options = income_menu(Decimal("1000.00"))
    assert "1.000" in text
    assert len(options) == 5


def test_resolve_choice_by_number():
    _, options = expense_menu(Decimal("50"))
    result = resolve_choice(1, options)
    assert result == ("Alimentação", None)


def test_resolve_choice_number_5():
    _, options = expense_menu(Decimal("50"))
    result = resolve_choice(5, options)
    assert result == ("Outros", None)


def test_resolve_choice_income_by_number():
    _, options = income_menu(Decimal("1000"))
    result = resolve_choice(2, options)
    assert result == ("Renda", "Freelance")


def test_resolve_choice_by_name():
    _, options = expense_menu(Decimal("50"))
    result = resolve_choice("alimentação", options)
    assert result == ("Alimentação", None)


def test_resolve_choice_by_name_case_insensitive():
    _, options = expense_menu(Decimal("50"))
    result = resolve_choice("TRANSPORTE", options)
    assert result == ("Transporte", None)


def test_resolve_invalid_number():
    _, options = expense_menu(Decimal("50"))
    assert resolve_choice(99, options) is None


def test_resolve_invalid_name():
    _, options = expense_menu(Decimal("50"))
    assert resolve_choice("xyz_unknown", options) is None
