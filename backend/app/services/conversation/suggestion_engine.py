"""Category suggestion menus shown when transaction category is ambiguous."""

from decimal import Decimal

_EXPENSE_OPTIONS: list[tuple[str, str | None]] = [
    ("Alimentação", None),
    ("Transporte", None),
    ("Moradia", None),
    ("Saúde", None),
    ("Outros", None),
]

_INCOME_OPTIONS: list[tuple[str, str | None]] = [
    ("Renda", "Salário"),
    ("Renda", "Freelance"),
    ("Renda", "Vendas"),
    ("Renda", "Investimentos"),
    ("Renda", None),
]


def expense_menu(amount: Decimal) -> tuple[str, list[tuple[str, str | None]]]:
    fmt = _fmt(amount)
    text = (
        f"Detectei uma despesa de {fmt}! Qual foi a categoria?\n\n"
        "1️⃣ Alimentação\n"
        "2️⃣ Transporte\n"
        "3️⃣ Moradia\n"
        "4️⃣ Saúde\n"
        "5️⃣ Outra\n\n"
        "Mande o número ou o nome!"
    )
    return text, list(_EXPENSE_OPTIONS)


def income_menu(amount: Decimal) -> tuple[str, list[tuple[str, str | None]]]:
    fmt = _fmt(amount)
    text = (
        f"Receita de {fmt}! Qual foi a fonte?\n\n"
        "1️⃣ Salário/Trabalho\n"
        "2️⃣ Freelance\n"
        "3️⃣ Venda\n"
        "4️⃣ Investimento\n"
        "5️⃣ Outro\n\n"
        "Escolha uma!"
    )
    return text, list(_INCOME_OPTIONS)


def resolve_choice(
    choice: int | str,
    options: list[tuple[str, str | None]],
) -> tuple[str, str | None] | None:
    """Resolve a numbered or named choice to (main, sub). Returns None if unresolved."""
    if isinstance(choice, int) and 1 <= choice <= len(options):
        return options[choice - 1]

    if isinstance(choice, str):
        from app.services.categorization.normalizer import normalize_text

        normalized = normalize_text(choice)
        for main, sub in options:
            if normalize_text(main) == normalized:
                return main, sub
            if sub and normalize_text(sub) == normalized:
                return main, sub
    return None


def _fmt(amount: Decimal) -> str:
    formatted = f"{amount:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")
