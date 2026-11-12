"""Shared text handling for the intelligence features.

Rule based on purpose. The brief says AI and ML are optional and that a well
designed rule based system is perfectly acceptable, and a deterministic
algorithm is something a team can explain line by line in a viva, which a model
checkpoint is not.
"""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    """
    a an the is are was were be been being am do does did doing have has had having
    i me my we our you your he she it its they them their this that these those
    and or but if then than so because as of at by for with about against between
    into through during to from up down in out on off over under again further
    not no nor only own same too very can will just should now there here when
    where why how all any both each few more most other some such
    please help issue problem unable cannot cant not working work broken getting
    get got need needs want trying tried since after before while also
    """.split()
)

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    words = _WORD.findall(text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def overlap_coefficient(left: set[str], right: set[str]) -> float:
    """Kinder than Jaccard when one title is much shorter than the other,
    which happens constantly: "payment down" against "the payment application
    is unavailable and users cannot complete transactions"."""
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def similarity(a_text: str, b_text: str) -> float:
    """Blend of both measures. Jaccard alone misses short reports, overlap
    alone fires on any two incidents sharing one word."""
    a, b = tokenize(a_text), tokenize(b_text)
    return round(0.4 * jaccard(a, b) + 0.6 * overlap_coefficient(a, b), 3)


def shared_terms(a_text: str, b_text: str, *, limit: int = 5) -> list[str]:
    return sorted(tokenize(a_text) & tokenize(b_text))[:limit]
