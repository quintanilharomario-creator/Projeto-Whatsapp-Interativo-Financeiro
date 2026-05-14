import re
from dataclasses import dataclass
from decimal import Decimal

from app.infrastructure.database.models.whatsapp_message import MessageType

_AMOUNT_RE = re.compile(
    r"R?\$?\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)",
    re.IGNORECASE,
)

_EXPENSE_KEYWORDS = re.compile(
    r"\b(gast\w+|pagu\w+|compr\w+|debit\w+|saiu|saída|despesa|d[ií]vida|boleto|paguei|gastei|comprei)\b",
    re.IGNORECASE,
)

_INCOME_KEYWORDS = re.compile(
    r"\b(recebi|ganhei|entrou|sal[aá]rio|renda|lucro|dep[oó]sito|transferência recebida|pix recebido)\b",
    re.IGNORECASE,
)

_QUERY_KEYWORDS = re.compile(
    r"\b(saldo|extrato|resumo|quanto|relat[oó]rio|gastos|sobrou|sobra|tenho)\b",
    re.IGNORECASE,
)

_CATEGORY_MAP = {
    re.compile(r"\b(mercado|supermercado|feira|aliment|comida|almoço|jantar|café|lanche|restaurante|ifood|delivery)\b", re.IGNORECASE): "Alimentação",
    re.compile(r"\b(uber|taxi|táxi|ônibus|onibus|metrô|metro|gasolina|combustível|combustivel|carro|estacionamento)\b", re.IGNORECASE): "Transporte",
    re.compile(r"\b(luz|energia|água|agua|internet|telefone|cel|aluguel|condomínio|condominio|iptu)\b", re.IGNORECASE): "Moradia",
    re.compile(r"\b(farmácia|farmacia|médico|medico|hospital|plano de saúde|plano saúde|consulta)\b", re.IGNORECASE): "Saúde",
    re.compile(r"\b(netflix|spotify|amazon|cinema|jogo|lazer|bar|show|entretenimento)\b", re.IGNORECASE): "Lazer",
    re.compile(r"\b(salário|salario|freela|freelance|renda|serviço prestado)\b", re.IGNORECASE): "Renda",
    re.compile(r"\b(escola|faculdade|curso|livro|material escolar)\b", re.IGNORECASE): "Educação",
    re.compile(r"\b(roupa|sapato|shopping|vestuário|vestuario)\b", re.IGNORECASE): "Vestuário",
}


@dataclass
class ParsedMessage:
    message_type: MessageType
    amount: Decimal | None
    category: str | None
    confidence: float


def _parse_amount(text: str) -> Decimal | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        value = Decimal(raw)
        return value if value > 0 else None
    except Exception:
        return None


def _detect_category(text: str) -> str | None:
    for pattern, category in _CATEGORY_MAP.items():
        if pattern.search(text):
            return category
    return "Outros"


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

        if is_expense and not is_income:
            return ParsedMessage(
                message_type=MessageType.EXPENSE,
                amount=amount,
                category=_detect_category(message_text),
                confidence=0.9 if amount else 0.6,
            )

        if is_income and not is_expense:
            return ParsedMessage(
                message_type=MessageType.INCOME,
                amount=amount,
                category=_detect_category(message_text),
                confidence=0.9 if amount else 0.6,
            )

        if amount:
            return ParsedMessage(
                message_type=MessageType.EXPENSE,
                amount=amount,
                category=_detect_category(message_text),
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
