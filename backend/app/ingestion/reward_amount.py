from __future__ import annotations

import re


_MONEY_PATTERN = re.compile(
    r"(?:\b(?:US|U\.S\.|USD|CA|CAD)\s*)?"
    r"\$\s*"
    r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)"
    r"\s*(billion|million|thousand|bn|[kmb])?\b",
    re.I,
)
_MULTIPLIERS = {
    "": 1,
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "b": 1_000_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}
_REWARD_TERMS = ("reward", "bounty")


def extract_cash_amount(
    text: str,
    *,
    require_reward_context: bool = False,
    context_characters: int = 180,
) -> int:
    amounts: list[int] = []
    for match in _MONEY_PATTERN.finditer(text or ""):
        if require_reward_context:
            context = text[
                max(0, match.start() - context_characters) :
                match.end() + context_characters
            ].lower()
            if not any(term in context for term in _REWARD_TERMS):
                continue

        numeric_value = float(match.group(1).replace(",", ""))
        multiplier = _MULTIPLIERS[(match.group(2) or "").lower()]
        amounts.append(round(numeric_value * multiplier))

    return max(amounts, default=0)
