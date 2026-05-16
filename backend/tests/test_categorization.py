"""Tests for the categorization package — normalizer, categorizer, and integration."""

from decimal import Decimal


from app.services.categorization.categorizer import CategoryResult, categorize
from app.services.categorization.normalizer import (
    normalize_text,
    parse_amount,
    preprocess_amount_text,
)


# ── normalize_text ─────────────────────────────────────────────────────────────


def test_normalize_removes_accents():
    assert normalize_text("Salário") == "salario"


def test_normalize_lowercases():
    assert normalize_text("MERCADO") == "mercado"


def test_normalize_collapses_triple_chars():
    assert normalize_text("mercadooo") == "mercadoo"


def test_normalize_removes_punctuation():
    result = normalize_text("gastei R$50!")
    assert "$" not in result and "!" not in result


def test_normalize_collapses_whitespace():
    assert normalize_text("  uber   25  ") == "uber 25"


# ── preprocess_amount_text ─────────────────────────────────────────────────────


def test_preprocess_1k():
    assert "1000" in preprocess_amount_text("1k de freela")


def test_preprocess_2k():
    assert "2000" in preprocess_amount_text("recebi 2k")


def test_preprocess_decimal_k():
    assert "1500" in preprocess_amount_text("1.5k de salário")


def test_preprocess_1mil():
    assert "1000" in preprocess_amount_text("1 mil de bônus")


def test_preprocess_decimal_mil():
    assert "1500" in preprocess_amount_text("1,5 mil de consultoria")


def test_preprocess_strips_contos():
    result = preprocess_amount_text("50 contos")
    assert "contos" not in result.lower()


def test_preprocess_strips_pilas():
    result = preprocess_amount_text("80 pilas")
    assert "pilas" not in result.lower()


# ── parse_amount ───────────────────────────────────────────────────────────────


def test_parse_amount_brl_format():
    assert parse_amount("R$ 1.500,00") == Decimal("1500.00")


def test_parse_amount_simple():
    assert parse_amount("gastei 50 no mercado") == Decimal("50")


def test_parse_amount_1k():
    assert parse_amount("1k de freela") == Decimal("1000")


def test_parse_amount_decimal_k():
    assert parse_amount("1.5k") == Decimal("1500")


def test_parse_amount_mil():
    assert parse_amount("1 mil de bônus") == Decimal("1000")


def test_parse_amount_contos():
    assert parse_amount("50 contos") == Decimal("50")


def test_parse_amount_returns_none_for_no_amount():
    assert parse_amount("qual meu saldo?") is None


# ── categorize — EXPENSE ───────────────────────────────────────────────────────


def test_categorize_expense_mercado():
    r = categorize("fui no mercado", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Mercado"


def test_categorize_expense_supermercado():
    r = categorize("comprei no supermercado", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Mercado"


def test_categorize_expense_fast_food():
    r = categorize("mcdonalds 35", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Fast Food"


def test_categorize_expense_fast_food_bk():
    r = categorize("paguei burger king", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Fast Food"


def test_categorize_expense_delivery():
    r = categorize("pedi no ifood", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Delivery"


def test_categorize_expense_bar():
    r = categorize("fui no boteco tomar cerveja", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Bar"


def test_categorize_expense_restaurante():
    r = categorize("almoço no restaurante", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Restaurante"


def test_categorize_expense_uber():
    r = categorize("uber 25", "EXPENSE")
    assert r.main == "Transporte"
    assert r.sub == "App"


def test_categorize_expense_gasolina():
    r = categorize("abasteci com gasolina", "EXPENSE")
    assert r.main == "Transporte"
    assert r.sub == "Combustível"


def test_categorize_expense_material_construcao():
    r = categorize("gastei 80 em material de construção", "EXPENSE")
    assert r.main == "Materiais"
    assert r.sub == "Construção"


def test_categorize_expense_material_eletrico():
    r = categorize("comprei material elétrico 200", "EXPENSE")
    assert r.main == "Materiais"
    assert r.sub == "Elétrica"


def test_categorize_expense_farmacia():
    r = categorize("remédio na farmácia", "EXPENSE")
    assert r.main == "Saúde"
    assert r.sub == "Farmácia"


def test_categorize_expense_consulta():
    r = categorize("consulta com dentista", "EXPENSE")
    assert r.main == "Saúde"
    assert r.sub == "Consultas"


def test_categorize_expense_netflix():
    r = categorize("netflix 39", "EXPENSE")
    assert r.main == "Lazer"
    assert r.sub == "Streaming"


def test_categorize_expense_spotify():
    r = categorize("spotify mensal", "EXPENSE")
    assert r.main == "Lazer"
    assert r.sub == "Streaming"


def test_categorize_expense_manicure():
    r = categorize("manicure 50", "EXPENSE")
    assert r.main == "Beleza"
    assert r.sub == "Unhas"


def test_categorize_expense_salao():
    r = categorize("fui ao salão cortar o cabelo", "EXPENSE")
    assert r.main == "Beleza"
    assert r.sub == "Cabelo"


def test_categorize_expense_veterinario():
    r = categorize("gastei 200 com veterinário", "EXPENSE")
    assert r.main == "Pets"
    assert r.sub == "Veterinário"


def test_categorize_expense_academia():
    r = categorize("paguei a academia", "EXPENSE")
    assert r.main == "Assinaturas"
    assert r.sub == "Academia"


def test_categorize_expense_moradia_luz():
    r = categorize("paguei conta de luz", "EXPENSE")
    assert r.main == "Moradia"


def test_categorize_expense_moradia_aluguel():
    r = categorize("paguei aluguel", "EXPENSE")
    assert r.main == "Moradia"
    assert r.sub == "Aluguel"


def test_categorize_expense_roupa():
    r = categorize("comprei roupa", "EXPENSE")
    assert r.main == "Vestuário"


def test_categorize_expense_fallback_outros():
    r = categorize("paguei alguma coisa estranha", "EXPENSE")
    assert r.main == "Outros"


# ── categorize — INCOME ────────────────────────────────────────────────────────


def test_categorize_income_salario():
    r = categorize("recebi salário", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Salário"


def test_categorize_income_holerite():
    r = categorize("caiu o holerite", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Salário"


def test_categorize_income_freelance():
    r = categorize("recebi 1000 de freelance", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Freelance"


def test_categorize_income_servico():
    r = categorize("recebi 500 de serviço", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Freelance"


def test_categorize_income_consultoria():
    r = categorize("ganhei 2000 de consultoria", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Freelance"


def test_categorize_income_freelance_beleza():
    r = categorize("recebi de uma unha que fiz", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Freelance - Beleza"


def test_categorize_income_freelance_tech():
    r = categorize("veio 500 do freela de site", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Freelance - Tech"


def test_categorize_income_venda():
    r = categorize("vendi um produto", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Vendas"


def test_categorize_income_investimento():
    r = categorize("rendimento de investimentos", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Investimentos"


def test_categorize_income_reembolso():
    r = categorize("recebi reembolso da empresa", "INCOME")
    assert r.main == "Renda"
    assert r.sub == "Reembolso"


# ── Typo tolerance ─────────────────────────────────────────────────────────────


def test_typo_mercadoo():
    r = categorize("gastei no mercadoo", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Mercado"


def test_typo_ubeer():
    r = categorize("ubeer 20", "EXPENSE")
    assert r.main == "Transporte"
    assert r.sub == "App"


def test_typo_uberr():
    r = categorize("uberr 20", "EXPENSE")
    assert r.main == "Transporte"
    assert r.sub == "App"


def test_fast_food_mecdonalds():
    r = categorize("fui no mecdonalds", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Fast Food"


def test_fast_food_macdonalds():
    r = categorize("macdonalds 30", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Fast Food"


def test_fast_food_burguer():
    r = categorize("paguei burguer king 25", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Fast Food"


def test_typo_edit_distance_mcdonalds():
    """'mcdonald' (missing 's') should still match via edit-distance."""
    r = categorize("fui no mcdonald", "EXPENSE")
    assert r.main == "Alimentação"
    assert r.sub == "Fast Food"


# ── CategoryResult ─────────────────────────────────────────────────────────────


def test_category_result_display_with_sub():
    r = CategoryResult(main="Alimentação", sub="Mercado", confidence=0.9)
    assert r.display == "Alimentação › Mercado"


def test_category_result_display_without_sub():
    r = CategoryResult(main="Outros", sub=None, confidence=0.1)
    assert r.display == "Outros"


def test_category_result_confidence_range():
    r = categorize("gastei 50 no mercado", "EXPENSE")
    assert 0.0 <= r.confidence <= 1.0
