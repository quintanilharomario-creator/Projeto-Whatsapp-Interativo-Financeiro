"""Unit tests for the conversational intent detector."""

import pytest

from app.services.conversation.intent_detector import (
    ConvIntent,
    detect,
    extract_edit_amounts,
)


# ── Confirm ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["sim", "SIM", "s", "yes", "confirma", "ok", "Ok!", "tá", "ta", "pode", "isso", "certo", "correto"])
def test_confirm_variants(text):
    intent, num = detect(text)
    assert intent == ConvIntent.CONFIRM
    assert num is None


# ── Deny ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["não", "nao", "no", "n", "nega", "nope", "errado", "cancela", "cancelar"])
def test_deny_variants(text):
    intent, num = detect(text)
    assert intent == ConvIntent.DENY
    assert num is None


# ── Number ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("1", 1), ("3", 3), ("9", 9),
    ("1️⃣", 1), ("2️⃣", 2), ("5️⃣", 5),
    ("2 alimentação", 2),
])
def test_number_variants(text, expected):
    intent, num = detect(text)
    assert intent == ConvIntent.NUMBER
    assert num == expected


# ── Delete ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "apaga essa despesa",
    "delete aquela receita",
    "remove o registro de 50",
    "tira a compra do mercado",
    "desfaz a transação de hoje",
    "apaga o último",
    "exclui aquela",
])
def test_delete_variants(text):
    intent, _ = detect(text)
    assert intent == ConvIntent.DELETE


# ── Edit ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "edita o valor de 50 para 75",
    "muda o valor",
    "corrige aquela despesa",
    "era 100, não 50",
    "era R$ 200 não era 180",
    "altera para 90",
    "atualiza o gasto",
])
def test_edit_variants(text):
    intent, _ = detect(text)
    assert intent == ConvIntent.EDIT


# ── None (regular message) ────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "gastei 50 no mercado",
    "recebi 1000 de salário",
    "qual meu saldo?",
    "olá tudo bem",
])
def test_none_for_regular_messages(text):
    intent, _ = detect(text)
    assert intent == ConvIntent.NONE


# ── extract_edit_amounts ──────────────────────────────────────────────────────

def test_extract_era_nao():
    new, old = extract_edit_amounts("era 100, não 50")
    assert new == 100.0
    assert old == 50.0


def test_extract_de_para():
    new, old = extract_edit_amounts("edita o valor de 50 para 75")
    assert new == 75.0
    assert old == 50.0


def test_extract_era_alone():
    new, old = extract_edit_amounts("era 200")
    assert new == 200.0
    assert old is None


def test_extract_para_alone():
    new, old = extract_edit_amounts("corrige para 80")
    assert new == 80.0
    assert old is None


def test_extract_no_amounts():
    new, old = extract_edit_amounts("corrige aquela despesa")
    assert new is None
    assert old is None
