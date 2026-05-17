import re
from decimal import Decimal, InvalidOperation
from enum import Enum

# ── Amount regex (same pattern as whatsapp_parser) ────────────────────────────

_AMOUNT_RE = re.compile(
    r"R?\$?\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)",
    re.IGNORECASE,
)

# ── Balance ───────────────────────────────────────────────────────────────────

_BALANCE_RE = re.compile(
    r"\b(saldo|meu saldo|saldo atual|quanto tenho|quanto eu tenho|to com quanto"
    r"|to com|dinheiro|conta|situa[cç][aã]o|status financeiro"
    r"|como estou|estou no (vermelho|azul)|sobrou quanto|quanto sobrou"
    r"|sobra|no azul|no vermelho|balan[cç]o)\b",
    re.IGNORECASE,
)

# ── Temporal ──────────────────────────────────────────────────────────────────

_TODAY_RE = re.compile(
    r"\b(hoje|de hoje|gastos? de hoje|quanto gastei hoje|gastos? hoje"
    r"|o que gastei hoje|o que eu gastei hoje)\b",
    re.IGNORECASE,
)

_YESTERDAY_RE = re.compile(
    r"\b(ontem|de ontem|gastos? de ontem|quanto gastei ontem|gastos? ontem"
    r"|anteontem|antes de ontem)\b",
    re.IGNORECASE,
)

_WEEK_RE = re.compile(
    r"\b(essa semana|esta semana|semana|da semana|da semana atual"
    r"|quanto gastei essa semana|gastos? da semana|gastos? dessa semana)\b",
    re.IGNORECASE,
)

_MONTH_RE = re.compile(
    r"\b(esse m[eê]s|este m[eê]s|do m[eê]s|desse m[eê]s|extrato do m[eê]s"
    r"|resumo do m[eê]s|quanto gastei esse m[eê]s|gastos? do m[eê]s"
    r"|como foi (meu|o) m[eê]s|resumo (do|desse) m[eê]s|m[eê]s atual)\b",
    re.IGNORECASE,
)

_LAST_MONTH_RE = re.compile(
    r"\b(m[eê]s passado|m[eê]s anterior|do m[eê]s passado|do m[eê]s anterior"
    r"|extrato do m[eê]s passado|quanto gastei m[eê]s passado)\b",
    re.IGNORECASE,
)

# ── Category query ────────────────────────────────────────────────────────────

_CATEGORY_KEYWORDS = [
    "alimenta[cç][aã]o",
    "comida",
    "mercado",
    "restaurante",
    "delivery",
    "transporte",
    "uber",
    "combustível",
    "combustivel",
    "gasolina",
    "moradia",
    "aluguel",
    "conta",
    "luz",
    "água",
    "agua",
    "internet",
    "saúde",
    "saude",
    "médico",
    "medico",
    "farmácia",
    "farmacia",
    "lazer",
    "entretenimento",
    "streaming",
    "viagem",
    "vestuário",
    "vestuario",
    "roupa",
    "roupas",
    "educação",
    "educacao",
    "curso",
    "escola",
    "outros",
]

_CATEGORY_QUERY_RE = re.compile(
    r"\b(quanto gastei com|gastos? com|minhas? despesas? com|"
    r"o que gastei com|gasto com|gastei com|despesas? com|"
    r"onde gasto mais|maior despesa|maior gasto|categorias?)\b",
    re.IGNORECASE,
)

_CATEGORY_NAMES_RE = re.compile(
    r"\b(" + "|".join(_CATEGORY_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# ── Planning ──────────────────────────────────────────────────────────────────

_PLANNING_RE = re.compile(
    r"\b(posso gastar|consigo (comprar|gastar|pagar)|"
    r"quanto posso gastar|quanto (eu )?posso gastar|"
    r"tenho (dinheiro|grana|verba) para|cabe no (bolso|or[cç]amento)|"
    r"sobra at[eé] (o )?final do m[eê]s|quanto sobra|"
    r"estou no or[cç]amento)\b",
    re.IGNORECASE,
)

# ── Greetings / Social ────────────────────────────────────────────────────────

_GREETING_RE = re.compile(
    r"^(oi|ol[aá]|e a[íi]|opa|hey|ei|al[oô]|bom dia|boa tarde|boa noite"
    r"|tudo bem|tudo bom|como vai|como voc[eê] est[aá]|como vc est[aá]"
    r"|tudo certo|tudo tranquilo|oiê)[!?.,\s]*$",
    re.IGNORECASE,
)

_THANKS_RE = re.compile(
    r"^(obrigad[ao]|obg|obrigad[ao]!|valeu|vlw|vl|muito obrigad[ao]"
    r"|thanks|thank you|brigad[ao])[!?.,\s]*$",
    re.IGNORECASE,
)

_GOODBYE_RE = re.compile(
    r"^(tchau|até|ate|até logo|ate logo|at[eé] mais|at[eé] depois"
    r"|até amanhã|ate amanha|abraços?|abra[cç]os?|flw|falou|foi|xau)[!?.,\s]*$",
    re.IGNORECASE,
)

# ── Help ──────────────────────────────────────────────────────────────────────

_HELP_RE = re.compile(
    r"^(ajuda|help|menu|comandos?|o que (voc[eê]|vc) (faz|sabe|pode|consegue)"
    r"|como funciona|o que [eé] isso|\?)[!?.,\s]*$",
    re.IGNORECASE,
)

# ── Insights ──────────────────────────────────────────────────────────────────

_INSIGHT_RE = re.compile(
    r"\b(me ajuda a economizar|como posso poupar|alguma dica|dica financeira"
    r"|analise meus gastos|analisa meus gastos|estou gastando muito"
    r"|como economizar|quero economizar mais|como t[aá] meus gastos"
    r"|como estão? meus gastos)\b",
    re.IGNORECASE,
)

# ── Goals ─────────────────────────────────────────────────────────────────────

_GOAL_CREATE_RE = re.compile(
    r"\b(quero economizar|criar meta|meta de|nova meta|definir meta"
    r"|minha meta [eé]|quero poupar)\b",
    re.IGNORECASE,
)

_GOAL_QUERY_RE = re.compile(
    r"\b(minha meta|como estou na meta|como t[aá] a meta|progresso da meta"
    r"|meta atual|ver meta|consultar meta)\b",
    re.IGNORECASE,
)

_GOAL_DELETE_RE = re.compile(
    r"\b(remover meta|deletar meta|apagar meta|cancelar meta|excluir meta"
    r"|sem meta|tira a meta|remove a meta)\b",
    re.IGNORECASE,
)


# ── Public enum and detector ──────────────────────────────────────────────────


class FinancialIntent(str, Enum):
    GREETING = "GREETING"
    THANKS = "THANKS"
    GOODBYE = "GOODBYE"
    HELP = "HELP"
    BALANCE = "BALANCE"
    TEMPORAL_TODAY = "TEMPORAL_TODAY"
    TEMPORAL_YESTERDAY = "TEMPORAL_YESTERDAY"
    TEMPORAL_WEEK = "TEMPORAL_WEEK"
    TEMPORAL_MONTH = "TEMPORAL_MONTH"
    TEMPORAL_LAST_MONTH = "TEMPORAL_LAST_MONTH"
    CATEGORY_QUERY = "CATEGORY_QUERY"
    PLANNING = "PLANNING"
    INSIGHT = "INSIGHT"
    GOAL_CREATE = "GOAL_CREATE"
    GOAL_QUERY = "GOAL_QUERY"
    GOAL_DELETE = "GOAL_DELETE"
    NONE = "NONE"


def _extract_amount(text: str) -> Decimal | None:
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        v = Decimal(raw)
        return v if v > 0 else None
    except InvalidOperation:
        return None


def _extract_category(text: str) -> str:
    m = _CATEGORY_NAMES_RE.search(text)
    return m.group(0).lower() if m else ""


def detect_financial_intent(text: str) -> tuple[FinancialIntent, dict]:
    """Return (FinancialIntent, extras_dict).

    Detection priority (highest first):
    GOODBYE > GREETING > THANKS > HELP > GOAL_DELETE > GOAL_QUERY > GOAL_CREATE
    > BALANCE > PLANNING > TEMPORAL_* > CATEGORY_QUERY > INSIGHT > NONE
    """
    t = text.strip()

    if _GOODBYE_RE.match(t):
        return FinancialIntent.GOODBYE, {}

    if _GREETING_RE.match(t):
        return FinancialIntent.GREETING, {}

    if _THANKS_RE.match(t):
        return FinancialIntent.THANKS, {}

    if _HELP_RE.match(t):
        return FinancialIntent.HELP, {}

    if _GOAL_DELETE_RE.search(t):
        return FinancialIntent.GOAL_DELETE, {}

    if _GOAL_QUERY_RE.search(t):
        return FinancialIntent.GOAL_QUERY, {}

    if _GOAL_CREATE_RE.search(t):
        amount = _extract_amount(t)
        return FinancialIntent.GOAL_CREATE, {"amount": amount}

    if _BALANCE_RE.search(t):
        return FinancialIntent.BALANCE, {}

    # Planning checked before temporal so "posso gastar hoje?" is PLANNING not TODAY
    if _PLANNING_RE.search(t):
        amount = _extract_amount(t)
        return FinancialIntent.PLANNING, {"amount": amount}

    # Temporal — order matters: LAST_MONTH before MONTH, YESTERDAY before TODAY
    if _LAST_MONTH_RE.search(t):
        return FinancialIntent.TEMPORAL_LAST_MONTH, {}

    if _MONTH_RE.search(t):
        return FinancialIntent.TEMPORAL_MONTH, {}

    if _WEEK_RE.search(t):
        return FinancialIntent.TEMPORAL_WEEK, {}

    if _YESTERDAY_RE.search(t):
        return FinancialIntent.TEMPORAL_YESTERDAY, {}

    if _TODAY_RE.search(t):
        return FinancialIntent.TEMPORAL_TODAY, {}

    if _CATEGORY_QUERY_RE.search(t):
        category = _extract_category(t)
        return FinancialIntent.CATEGORY_QUERY, {"category": category}

    if _INSIGHT_RE.search(t):
        return FinancialIntent.INSIGHT, {}

    return FinancialIntent.NONE, {}
