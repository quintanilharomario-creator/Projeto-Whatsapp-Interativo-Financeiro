import re

# Detects amounts in Brazilian format (matches same pattern as whatsapp_parser)
_AMOUNT_RE = re.compile(
    r"R?\$?\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)",
    re.IGNORECASE,
)

# Connectors that split multiple transactions
_CONNECTOR_RE = re.compile(
    r"\s*(?:,\s*|\s+e\s+|\s+mais\s+|\s*;\s*)",
    re.IGNORECASE,
)

# Transaction verbs that can introduce a segment
_VERB_RE = re.compile(
    r"\b(gast\w+|pagu\w+|compr\w+|recebi|ganhei|entrou|caiu|faturei|embolsei"
    r"|lucrei|torrei|desembolsei|dep[oó]sito)\b",
    re.IGNORECASE,
)


def split_transactions(text: str) -> list[str] | None:
    """Split a message with multiple transactions into individual messages.

    Returns None if only one transaction is found (caller should use normal parse).
    Returns a list of ≥2 strings, each parseable as a single transaction.

    Strategy:
    - Find all amount positions in the text
    - If ≤1 amount → None
    - Split on connectors near each amount to get segments
    - Inherit the verb from the first segment if subsequent ones lack one
    """
    amounts = list(_AMOUNT_RE.finditer(text))
    if len(amounts) < 2:
        return None

    # Split the text on connectors to get candidate segments
    segments = _CONNECTOR_RE.split(text)
    # Each segment must contain at least one amount to be valid
    valid = [s.strip() for s in segments if s.strip() and _AMOUNT_RE.search(s)]

    if len(valid) < 2:
        return None

    # Detect the leading verb from the first valid segment
    first_verb_m = _VERB_RE.search(valid[0])
    leading_verb = first_verb_m.group(0) if first_verb_m else "gastei"

    result = []
    for seg in valid:
        seg = seg.strip()
        if not seg:
            continue
        # If segment has no verb, prepend the leading verb
        if not _VERB_RE.search(seg):
            seg = f"{leading_verb} {seg}"
        result.append(seg)

    return result if len(result) >= 2 else None
