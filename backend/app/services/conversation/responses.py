from datetime import datetime
from decimal import Decimal

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

_CATEGORY_EMOJI = {
    "alimentação": "🍔",
    "transporte": "🚗",
    "moradia": "🏠",
    "saúde": "🏥",
    "lazer": "🎬",
    "educação": "📚",
    "vestuário": "👕",
    "outros": "💳",
    "renda": "💰",
}


def _fmt(amount: Decimal) -> str:
    formatted = f"{amount:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _first_name(full_name: str | None) -> str:
    if not full_name:
        return ""
    return full_name.split()[0]


def _cat_emoji(cat: str) -> str:
    return _CATEGORY_EMOJI.get(cat.lower(), "💳")


def _days_left_in_month(now: datetime) -> int:
    import calendar

    last_day = calendar.monthrange(now.year, now.month)[1]
    return max(0, last_day - now.day)


# ── Balance ───────────────────────────────────────────────────────────────────


def format_balance(
    balance: dict,
    monthly: dict,
    now: datetime,
    user_name: str | None = None,
) -> str:
    name = _first_name(user_name)
    month_name = _MONTH_NAMES_PT[now.month]
    bal = balance["balance"]
    income = monthly["total_income"]
    expense = monthly["total_expense"]
    monthly_bal = monthly["balance"]

    name_line = f", {name}" if name else ""
    savings_pct = (
        int(monthly_bal / income * 100) if income > 0 and monthly_bal > 0 else 0
    )
    savings_line = (
        f"\n📈 Você economizou *{savings_pct}%* das receitas este mês! 🎉"
        if savings_pct > 0
        else ""
    )

    return (
        f"💰 *Seu saldo atual{name_line}: {_fmt(bal)}*\n\n"
        f"📊 *Resumo de {month_name}/{now.year}:*\n"
        f"✅ Receitas: {_fmt(income)}\n"
        f"❌ Despesas: {_fmt(expense)}\n"
        f"📈 Saldo do mês: {'+' if monthly_bal >= 0 else ''}{_fmt(monthly_bal)}"
        f"{savings_line}\n\n"
        f"💡 Você ainda tem *{_fmt(bal)}* disponíveis!"
    )


# ── Temporal summaries ────────────────────────────────────────────────────────


def format_temporal_summary(
    transactions: list,
    label: str,
    now: datetime,
) -> str:
    if not transactions:
        return f"📅 *{label}*\n\nNenhum gasto registrado neste período."

    expenses = [t for t in transactions if str(t.type).endswith("EXPENSE")]
    income_txns = [t for t in transactions if str(t.type).endswith("INCOME")]

    total_expense = sum(t.amount for t in expenses)
    total_income = sum(t.amount for t in income_txns)

    lines = [f"📅 *{label}*"]

    if expenses:
        lines.append(f"💸 Total gasto: *{_fmt(total_expense)}*")
        lines.append(f"📊 {len(expenses)} transação(ões) registrada(s)")
        if len(expenses) <= 8:
            lines.append("")
            for t in expenses:
                emoji = _cat_emoji(t.category)
                lines.append(f"{emoji} {_fmt(t.amount)} - {t.category}")

    if income_txns:
        lines.append(f"\n💰 Total recebido: *{_fmt(total_income)}*")

    return "\n".join(lines)


# ── Monthly full summary ──────────────────────────────────────────────────────


def format_monthly_full(monthly: dict, now: datetime) -> str:
    month_name = _MONTH_NAMES_PT[now.month]
    income = monthly["total_income"]
    expense = monthly["total_expense"]
    bal = monthly["balance"]
    by_cat = monthly.get("by_category", [])

    savings_pct = int(bal / income * 100) if income > 0 and bal > 0 else 0
    savings_line = (
        f"\n📈 Você economizou *{savings_pct}%* das receitas! 🎉"
        if savings_pct > 0
        else ""
    )

    lines = [
        f"📊 *{month_name}/{now.year} — Resumo Completo*\n",
        f"💰 Receitas: *{_fmt(income)}*",
        f"❌ Despesas: *{_fmt(expense)}*",
        f"✅ Saldo: *{_fmt(bal)}*",
    ]

    if by_cat:
        lines.append("\n*Top categorias:*")
        for cat in by_cat[:5]:
            emoji = _cat_emoji(cat["category"])
            pct = int(cat["percentage"])
            lines.append(f"{emoji} {cat['category']}: {_fmt(cat['total'])} ({pct}%)")

    lines.append(savings_line)
    return "\n".join(lines)


# ── Category breakdown ────────────────────────────────────────────────────────


def format_category_breakdown(
    category: str,
    transactions: list,
    monthly_total_expense: Decimal,
    now: datetime,
) -> str:
    month_name = _MONTH_NAMES_PT[now.month]
    cat_display = category.capitalize() if category else "Categoria"
    emoji = _cat_emoji(category)

    if not transactions:
        return (
            f"{emoji} *{cat_display} — {month_name}/{now.year}*\n\n"
            f"Nenhum gasto registrado nesta categoria."
        )

    total = sum(t.amount for t in transactions)
    pct = int(total / monthly_total_expense * 100) if monthly_total_expense > 0 else 0

    # Sub-category breakdown
    sub_totals: dict[str, Decimal] = {}
    for t in transactions:
        sub = getattr(t, "subcategory", None) or t.category
        sub_totals[sub] = sub_totals.get(sub, Decimal("0")) + t.amount

    lines = [
        f"{emoji} *{cat_display} — {month_name}/{now.year}*\n",
        f"Total gasto: *{_fmt(total)}*",
        f"📊 {pct}% das suas despesas",
    ]

    if len(sub_totals) > 1:
        lines.append("\n*Detalhamento:*")
        for sub, sub_total in sorted(sub_totals.items(), key=lambda x: -x[1]):
            sub_pct = int(sub_total / total * 100) if total > 0 else 0
            lines.append(f"• {sub}: {_fmt(sub_total)} ({sub_pct}%)")

    return "\n".join(lines)


# ── Planning ──────────────────────────────────────────────────────────────────


def format_planning_can(amount: Decimal, balance: Decimal, now: datetime) -> str:
    days_left = _days_left_in_month(now)
    after = balance - amount
    daily = after / days_left if days_left > 0 else after

    return (
        f"🤔 *Análise: Gastar {_fmt(amount)}*\n\n"
        f"✅ Você TEM esse valor disponível!\n"
        f"💰 Saldo atual: *{_fmt(balance)}*\n"
        f"📊 Após o gasto: *{_fmt(after)}*\n\n"
        f"📅 Faltam {days_left} dia(s) até fim do mês\n"
        f"💡 Daria *{_fmt(daily)}/dia* restantes\n\n"
        f"✅ *Pode gastar tranquilamente!*"
    )


def format_planning_cannot(amount: Decimal, balance: Decimal) -> str:
    lack = amount - balance
    return (
        f"🤔 *Análise: Gastar {_fmt(amount)}*\n\n"
        f"🚨 Atenção! Valor maior que seu saldo\n"
        f"💰 Saldo atual: *{_fmt(balance)}*\n"
        f"❌ Faltariam: *{_fmt(lack)}*\n\n"
        f"💡 Sugestões:\n"
        f"1️⃣ Aguardar próxima receita\n"
        f"2️⃣ Gastar valor menor ({_fmt(balance * Decimal('0.8'))})\n"
        f"3️⃣ Revisar despesas deste mês"
    )


# ── Greetings ─────────────────────────────────────────────────────────────────


def format_greeting(
    user_name: str | None,
    balance: Decimal,
    now: datetime,
) -> str:
    from datetime import timezone

    hour = now.astimezone(timezone.utc).hour
    # Adjust for Brazil timezone (UTC-3)
    hour_br = (hour - 3) % 24

    if hour_br < 12:
        saudacao = "☀️ Bom dia"
    elif hour_br < 18:
        saudacao = "🌤️ Boa tarde"
    else:
        saudacao = "🌙 Boa noite"

    name = _first_name(user_name)
    name_str = f", {name}" if name else ""

    return (
        f"{saudacao}{name_str}!\n\n"
        f"💰 Saldo atual: *{_fmt(balance)}*\n\n"
        f"O que vai registrar hoje?\n"
        f"💸 'gastei X no Y' — Despesa\n"
        f"💰 'recebi X de Y' — Receita\n"
        f"📊 'saldo' — Ver situação"
    )


def format_thanks(user_name: str | None) -> str:
    name = _first_name(user_name)
    name_str = f", {name}" if name else ""
    return f"😊 De nada{name_str}!\nSempre que precisar, é só me chamar! 💪"


def format_goodbye(
    user_name: str | None,
    balance: Decimal,
    now: datetime,
) -> str:
    name = _first_name(user_name)
    name_str = f", {name}" if name else ""
    days_left = _days_left_in_month(now)
    return (
        f"👋 Até logo{name_str}!\n\n"
        f"💰 Saldo atual: *{_fmt(balance)}*\n"
        f"📅 Faltam {days_left} dia(s) até fim do mês\n\n"
        f"Qualquer coisa é só me chamar! 🚀"
    )


# ── Help menu ─────────────────────────────────────────────────────────────────


def format_help() -> str:
    return (
        "🤖 *Olá! Sou o Hermes, seu gerente financeiro!*\n\n"
        "*📝 REGISTROS:*\n"
        "💰 'recebi 1000 de salário'\n"
        "💸 'gastei 50 no mercado'\n"
        "🎤 Mande áudio também!\n\n"
        "*📊 CONSULTAS:*\n"
        "💰 'qual meu saldo?'\n"
        "📅 'gastos de hoje'\n"
        "📊 'resumo do mês'\n"
        "🏷️ 'quanto gastei com alimentação'\n\n"
        "*🎯 PLANEJAMENTO:*\n"
        "💡 'posso gastar 500?'\n"
        "🎯 'quero economizar 1000'\n"
        "📈 'minha meta'\n\n"
        "*✏️ EDIÇÃO:*\n"
        "🗑️ 'apaga o último'\n"
        "✏️ 'era 100, não 50'\n\n"
        "*💡 INSIGHTS:*\n"
        "🤔 'me ajuda a economizar'\n"
        "📊 'analise meus gastos'\n\n"
        "Quer testar? Manda qualquer comando! 🚀"
    )


# ── Multiple transactions ─────────────────────────────────────────────────────


def format_multi_transactions(
    results: list[tuple[str, Decimal, str]],
    balance: Decimal,
) -> str:
    """results: list of (type_label, amount, cat_display)"""
    count = len(results)
    lines = [f"✅ *{count} transações registradas:*\n"]
    for i, (type_label, amount, cat_display) in enumerate(results, 1):
        icon = "💰" if type_label == "receita" else "💸"
        lines.append(f"{icon} {i}️⃣ {_fmt(amount)} — {cat_display}")
    lines.append(f"\n💰 Saldo atual: *{_fmt(balance)}*")
    return "\n".join(lines)


# ── Goals ─────────────────────────────────────────────────────────────────────


def format_goal_created(
    target: Decimal,
    saved: Decimal,
    period_end: datetime,
) -> str:
    days_left = max(0, (period_end.date() - datetime.now().date()).days)
    remaining = max(Decimal("0"), target - saved)
    daily_needed = remaining / days_left if days_left > 0 else remaining

    lines = [
        "🎯 *Meta criada!*\n",
        f"✅ Economizar *{_fmt(target)}*",
        f"📊 Você já economizou: *{_fmt(saved)}*",
        f"💪 Falta: *{_fmt(remaining)}*",
        f"📅 Em {days_left} dia(s)",
    ]
    if daily_needed > 0:
        lines.append(f"\n💡 Para alcançar: economizar *{_fmt(daily_needed)}/dia*")

    return "\n".join(lines)


def format_goal_progress(
    target: Decimal,
    saved: Decimal,
    period_end: datetime,
) -> str:
    pct = min(100, int(saved / target * 100)) if target > 0 else 0
    bar_filled = pct // 10
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    remaining = max(Decimal("0"), target - saved)
    days_left = max(0, (period_end.date() - datetime.now().date()).days)

    on_track_line = ""
    if pct >= 100:
        on_track_line = "\n🎉 *Meta atingida! Parabéns!*"
    elif days_left > 0:
        expected_pct = max(0, 100 - int(days_left / 30 * 100))
        if pct >= expected_pct:
            on_track_line = (
                f"\n📈 Você está {pct - expected_pct}% acima do esperado! 🎉"
            )
        else:
            on_track_line = "\n💪 Continue assim, você consegue!"

    return (
        f"🎯 *Sua meta: Economizar {_fmt(target)}*\n\n"
        f"📊 Progresso: {bar} {pct}%\n"
        f"💰 Economizado: *{_fmt(saved)}*\n"
        f"🎯 Falta: *{_fmt(remaining)}*"
        f"{on_track_line}"
    )


def format_no_goal() -> str:
    return (
        "🎯 Você ainda não tem uma meta ativa.\n\n"
        "Para criar uma, diga:\n"
        "_'quero economizar 1000 esse mês'_"
    )


def format_goal_deleted() -> str:
    return "🗑️ Meta removida com sucesso!\n\nCrie uma nova quando quiser. 💪"


def format_goal_not_found() -> str:
    return (
        "🎯 Você não tem nenhuma meta ativa.\n\n"
        "Para criar: _'quero economizar 1000 esse mês'_"
    )
