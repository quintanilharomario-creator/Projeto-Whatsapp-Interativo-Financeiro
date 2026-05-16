"""Transaction categorizer using keyword scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.categorization.library import EXPENSE_ENTRIES, INCOME_ENTRIES
from app.services.categorization.normalizer import fuzzy_words, normalize_text

_ALL_REPEATED = re.compile(r"(.)\1+")


@dataclass
class CategoryResult:
    main: str
    sub: str | None
    confidence: float

    @property
    def display(self) -> str:
        return f"{self.main} › {self.sub}" if self.sub else self.main


def _score_entry(
    normalized: str,
    exact_words: frozenset[str],
    fuzzy: frozenset[str],
    keywords: list[str],
) -> float:
    score = 0.0
    for kw in keywords:
        kw_norm = normalize_text(kw)
        kw_parts = kw_norm.split()
        if len(kw_parts) == 1:
            kw_fuzzy = _ALL_REPEATED.sub(r"\1", kw_norm)
            if kw_norm in exact_words or kw_fuzzy in fuzzy:
                score += 1.0
        else:
            # Multi-word phrase: substring match in normalized text
            phrase = " ".join(kw_parts)
            if phrase in normalized:
                score += len(kw_parts) * 1.5
    return score


def categorize(text: str, transaction_type: str) -> CategoryResult:
    """Return the best-matching category for *text* given *transaction_type*.

    Args:
        text: Raw user message.
        transaction_type: ``"EXPENSE"`` or ``"INCOME"``.

    Returns:
        :class:`CategoryResult` with main category, optional subcategory,
        and a 0–1 confidence score.
    """
    normalized = normalize_text(text)
    exact = frozenset(normalized.split())
    fuzzy = fuzzy_words(normalized)

    entries = INCOME_ENTRIES if transaction_type == "INCOME" else EXPENSE_ENTRIES

    best_score = 0.0
    best_main = "Outros"
    best_sub: str | None = None

    for main, sub, keywords in entries:
        score = _score_entry(normalized, exact, fuzzy, keywords)
        if score > best_score:
            best_score = score
            best_main = main
            best_sub = sub

    max_possible = 5.0  # generous ceiling for confidence normalisation
    confidence = min(1.0, best_score / max_possible)
    return CategoryResult(main=best_main, sub=best_sub, confidence=confidence)
