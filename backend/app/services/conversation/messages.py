"""Friendly message templates for the conversational WhatsApp flow."""

from decimal import Decimal

NOT_UNDERSTOOD = (
    "Desculpa, não consegui entender! 😅\n\n"
    "Você pode me dizer:\n"
    "📝 Gastos: 'gastei 50 no mercado'\n"
    "📝 Receitas: 'recebi 100 de freelance'\n"
    "📝 Saldo: 'qual meu saldo?'\n"
    "📝 Apagar: 'apaga esse gasto'\n"
    "📝 Editar: 'era 100, não 50'\n\n"
    "Tenta de novo? 💪"
)

NO_TRANSACTION_TO_ACT_ON = (
    "Não encontrei nenhuma transação recente. "
    "Registre alguma receita ou despesa primeiro!"
)

NOTHING_CHANGED = "Tudo bem, nada foi alterado! 😊"

NO_ACTIVE_STATE = (
    "Não há nenhuma ação pendente. "
    "Me diga o que você quer fazer!"
)

ASK_AMOUNT = "Qual foi o valor? 💰"

INVALID_CHOICE = (
    "Não reconheci essa opção. "
    "Por favor, mande o número correspondente (1, 2, 3...) ou o nome da categoria."
)


def delete_confirm(type_label: str, amount: Decimal, category: str) -> str:
    fmt = _fmt(amount)
    return (
        f"Vou apagar a {type_label} de {fmt} em {category}.\n\n"
        "Confirma? Mande SIM ou NÃO"
    )


def delete_success(type_label: str, balance: Decimal) -> str:
    return (
        f"✓ {type_label.capitalize()} apagada com sucesso!\n"
        f"Seu saldo agora é: {_fmt(balance)}"
    )


def edit_confirm(old_amount: Decimal, new_amount: Decimal) -> str:
    return (
        f"Vou corrigir de {_fmt(old_amount)} para {_fmt(new_amount)}.\n\n"
        "Confirma? Mande SIM ou NÃO"
    )


def edit_success(new_amount: Decimal, balance: Decimal) -> str:
    return (
        f"✓ Transação atualizada!\n"
        f"Novo valor: {_fmt(new_amount)}\n"
        f"Seu saldo agora é: {_fmt(balance)}"
    )


def transaction_registered(
    type_label: str,
    amount: Decimal,
    cat_display: str,
    balance: Decimal,
) -> str:
    return (
        f"✓ {type_label.capitalize()} de {_fmt(amount)} "
        f"em {cat_display} registrada!\n"
        f"Seu saldo agora é: {_fmt(balance)}"
    )


def _fmt(amount: Decimal) -> str:
    formatted = f"{amount:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")
