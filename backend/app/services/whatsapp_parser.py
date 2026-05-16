import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.infrastructure.database.models.whatsapp_message import MessageType

# ── Type-detection regex (income / expense / query) ───────────────────────────

_EXPENSE_KEYWORDS = re.compile(
    r"\b(gast\w+|pagu\w+|compr\w+|debit\w+|saiu|sa[ií]da|despesa|d[ií]vida"
    r"|boleto|paguei|gastei|comprei|torrei|desembolsei|custou)\b",
    re.IGNORECASE,
)

_INCOME_KEYWORDS = re.compile(
    r"\b(recebi|ganhei|entrou|caiu|faturei|embolsei|lucrei|captei|arrecadei"
    r"|sal[aá]rio|renda|lucro|dep[oó]sito|transferência recebida|pix recebido"
    r"|pingou|veio|freela|freelance|holerite|dividendos|rendimento)\b",
    re.IGNORECASE,
)

_QUERY_KEYWORDS = re.compile(
    r"\b(saldo|extrato|resumo|quanto|relat[oó]rio|gastos|sobrou|sobra|tenho"
    r"|balan[cç]o|movimenta\w*|transa\w*)\b",
    re.IGNORECASE,
)

# ── Amount regex (handles Brazilian formats + informal amounts via normalizer) ─

_AMOUNT_RE = re.compile(
    r"R?\$?\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)",
    re.IGNORECASE,
)


@dataclass
class ParsedMessage:
    message_type: MessageType
    amount: Decimal | None
    category: str | None
    confidence: float
    subcategory: str | None = field(default=None)


def _parse_amount(text: str) -> Decimal | None:
    from app.services.categorization.normalizer import preprocess_amount_text

    preprocessed = preprocess_amount_text(text)
    match = _AMOUNT_RE.search(preprocessed)
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        value = Decimal(raw)
        return value if value > 0 else None
    except Exception:
        return None


def _detect_category(text: str, transaction_type: str) -> tuple[str, str | None]:
    """Return (main_category, subcategory) using the categorization library."""
    from app.services.categorization.categorizer import categorize

    result = categorize(text, transaction_type)
    return result.main, result.sub


class WhatsappParser:
    @staticmethod
    def parse(message_text: str) -> ParsedMessage:
        is_expense = bool(_EXPENSE_KEYWORDS.search(message_text))
        is_income = bool(_INCOME_KEYWORDS.search(message_text))
        is_query = bool(_QUERY_KEYWORDS.search(message_text))

        amount = _parse_amount(message_text)

        if is_query and not (is_expense or is_income):
            return ParsedMessage(
                message_type=MessageType.QUERY,
                amount=None,
                category=None,
                confidence=0.9,
            )

        # Expense verbs are explicit actions and take priority over income
        # category keywords when both are present (e.g. "gastei com freela").
        if is_expense:
            main, sub = _detect_category(message_text, "EXPENSE")
            return ParsedMessage(
                message_type=MessageType.EXPENSE,
                amount=amount,
                category=main,
                subcategory=sub,
                confidence=0.9 if amount else 0.6,
            )

        if is_income and not is_expense:
            main, sub = _detect_category(message_text, "INCOME")
            return ParsedMessage(
                message_type=MessageType.INCOME,
                amount=amount,
                category=main,
                subcategory=sub,
                confidence=0.9 if amount else 0.6,
            )

        if amount:
            main, sub = _detect_category(message_text, "EXPENSE")
            return ParsedMessage(
                message_type=MessageType.EXPENSE,
                amount=amount,
                category=main,
                subcategory=sub,
                confidence=0.4,
            )

        return ParsedMessage(
            message_type=MessageType.OTHER,
            amount=None,
            category=None,
            confidence=1.0,
        )

    @staticmethod
    async def parse_with_ai(message_text: str, ai_service) -> ParsedMessage:
        """Parse using AI first, falling back to regex on failure."""
        try:
            from app.infrastructure.database.models.transaction import TransactionType

            suggestion = await ai_service.analyze_transaction(message_text)
            msg_type = (
                MessageType.INCOME
                if suggestion.type == TransactionType.INCOME
                else MessageType.EXPENSE
            )
            return ParsedMessage(
                message_type=msg_type,
                amount=suggestion.amount,
                category=suggestion.category,
                confidence=suggestion.confidence,
            )
        except Exception:
            return WhatsappParser.parse(message_text)
