"""Detect high-level conversational intents before normal message parsing."""

import re
from enum import Enum


class ConvIntent(str, Enum):
    DELETE = "DELETE"
    EDIT = "EDIT"
    CONFIRM = "CONFIRM"
    DENY = "DENY"
    NUMBER = "NUMBER"
    NONE = "NONE"


_DELETE_RE = re.compile(
    r"\b(apaga|apagar|deleta|deletar|delete|remove|remover|tira|tirar"
    r"|desfaz|desfazer|exclui|excluir|apague|remova)\b",
    re.IGNORECASE,
)
_EDIT_RE = re.compile(
    r"\b(edita|editar|muda|mudar|corrige|corrigir|altera|alterar|atualiza|atualizar)\b"
    r"|era\s+R?\$?\s*[\d,.]+",
    re.IGNORECASE,
)
_CONFIRM_RE = re.compile(
    r"^\s*(sim|s|yes|y|confirma|confirmo|ok|tá|ta|pode|isso|certo|correto|exato|claro)\s*[!.]*\s*$",
    re.IGNORECASE,
)
_DENY_RE = re.compile(
    r"^\s*(n[aã]o|no|n|nega|nope|errado|errada|negativo|cancela|cancelar)\s*[!.]*\s*$",
    re.IGNORECASE,
)

_EMOJI_DIGITS: dict[str, int] = {
    "1️⃣": 1, "2️⃣": 2, "3️⃣": 3, "4️⃣": 4, "5️⃣": 5,
    "6️⃣": 6, "7️⃣": 7, "8️⃣": 8, "9️⃣": 9,
}


def detect(text: str) -> tuple[ConvIntent, int | None]:
    """Return (intent, menu_number). menu_number is only set for NUMBER."""
    stripped = text.strip()

    if _CONFIRM_RE.match(stripped):
        return ConvIntent.CONFIRM, None
    if _DENY_RE.match(stripped):
        return ConvIntent.DENY, None

    # Pure digit 1-9
    if re.match(r"^[1-9]$", stripped):
        return ConvIntent.NUMBER, int(stripped)
    # Emoji digit
    if stripped in _EMOJI_DIGITS:
        return ConvIntent.NUMBER, _EMOJI_DIGITS[stripped]
    # "2 alimentação" style — number at the very start
    m = re.match(r"^([1-9])\s+\w", stripped)
    if m:
        return ConvIntent.NUMBER, int(m.group(1))

    if _DELETE_RE.search(stripped):
        return ConvIntent.DELETE, None
    if _EDIT_RE.search(stripped):
        return ConvIntent.EDIT, None

    return ConvIntent.NONE, None


def extract_edit_amounts(text: str) -> tuple[float | None, float | None]:
    """Extract (new_amount, old_hint) from edit messages.

    'era 100, não 50' → (100, 50)
    'de 50 para 75'   → (75, 50)
    'corrige para 80' → (80, None)
    """
    # "era X, não Y" — X is the correct value
    m = re.search(
        r"era\s+R?\$?\s*([\d,.]+)[,\s]*(?:n[aã]o|e\s+n[aã]o)\s+R?\$?\s*([\d,.]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return _to_float(m.group(1)), _to_float(m.group(2))

    # "de X para Y"
    m = re.search(
        r"de\s+R?\$?\s*([\d,.]+)\s+(?:para|pra)\s+R?\$?\s*([\d,.]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return _to_float(m.group(2)), _to_float(m.group(1))

    # "era X" alone
    m = re.search(r"era\s+R?\$?\s*([\d,.]+)", text, re.IGNORECASE)
    if m:
        return _to_float(m.group(1)), None

    # "para X" / "pra X"
    m = re.search(r"(?:para|pra)\s+R?\$?\s*([\d,.]+)", text, re.IGNORECASE)
    if m:
        return _to_float(m.group(1)), None

    return None, None


def _to_float(raw: str) -> float | None:
    try:
        return float(raw.replace(".", "").replace(",", "."))
    except ValueError:
        return None
