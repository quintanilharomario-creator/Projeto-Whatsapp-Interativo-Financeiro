"""Text normalization and amount preprocessing for Brazilian Portuguese."""

import re
from decimal import Decimal, InvalidOperation

from unidecode import unidecode

# ── Amount preprocessing ───────────────────────────────────────────────────────

# Applied before the main amount regex to expand informal formats.
_K_DECIMAL_RE = re.compile(r"\b(\d+)[.,](\d+)\s*k\b", re.IGNORECASE)
_K_RE = re.compile(r"\b(\d+)\s*k\b", re.IGNORECASE)
_MIL_DECIMAL_RE = re.compile(r"\b(\d+)[.,](\d+)\s*mil\b", re.IGNORECASE)
_MIL_RE = re.compile(r"\b(\d+)\s*mil\b", re.IGNORECASE)

# Informal currency words that follow an amount ("50 contos", "80 paus")
_INFORMAL_CURRENCY_RE = re.compile(r"\b(contos?|pilas?|paus?|mangos?)\b", re.IGNORECASE)

# ── Text normalization ─────────────────────────────────────────────────────────

_REPEATED_CHARS_RE = re.compile(r"(.)\1{2,}")
_ALL_REPEATED_RE = re.compile(r"(.)\1+")
_NON_WORD_RE = re.compile(r"[^\w\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")


def remove_accents(text: str) -> str:
    return unidecode(text)


def preprocess_amount_text(text: str) -> str:
    """Expand informal number variants before running the amount regex.

    Examples: "1k" → "1000", "1.5k" → "1500", "1 mil" → "1000".
    """
    text = _K_DECIMAL_RE.sub(
        lambda m: str(round(float(f"{m.group(1)}.{m.group(2)}") * 1000)), text
    )
    text = _K_RE.sub(lambda m: str(int(m.group(1)) * 1000), text)
    text = _MIL_DECIMAL_RE.sub(
        lambda m: str(round(float(f"{m.group(1)}.{m.group(2)}") * 1000)), text
    )
    text = _MIL_RE.sub(lambda m: str(int(m.group(1)) * 1000), text)
    text = _INFORMAL_CURRENCY_RE.sub("", text)
    return text


def normalize_text(text: str) -> str:
    """Normalize text for keyword matching.

    Pipeline: lowercase → remove accents → collapse 3+ repeated chars →
    remove punctuation → normalize whitespace.
    """
    text = text.lower()
    text = remove_accents(text)
    text = _REPEATED_CHARS_RE.sub(r"\1\1", text)  # "mercadooo" → "mercadoo"
    text = _NON_WORD_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text


def fuzzy_words(normalized: str) -> frozenset[str]:
    """Return word set with all repeated chars collapsed (for typo tolerance).

    "mercadoo" → "mercado", allowing it to match the keyword "mercado".
    """
    return frozenset(_ALL_REPEATED_RE.sub(r"\1", w) for w in normalized.split())


def parse_amount(text: str) -> Decimal | None:
    """Extract a monetary amount from raw text, handling informal variants."""
    preprocessed = preprocess_amount_text(text)
    match = re.search(
        r"R?\$?\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)",
        preprocessed,
        re.IGNORECASE,
    )
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        value = Decimal(raw)
        return value if value > 0 else None
    except InvalidOperation:
        return None
