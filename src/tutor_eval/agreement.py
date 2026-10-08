"""How well does the AI judge agree with Sara (the human labeller)?

Cohen's kappa = agreement corrected for chance. 1 = perfect, 0 = no better than two
labellers guessing with the same habits, below 0 = worse than chance.
- Yes/no criteria (answer leak, escalation) use plain kappa.
- 1-5 scores (scaffolding, age fit, language) use quadratic-weighted kappa, where a 4-vs-5
  disagreement counts much less than a 1-vs-5 one.

Written by hand (not imported) so every step can be explained; tests/test_agreement.py
checks it against scikit-learn.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


def cohen_kappa(a: Sequence, b: Sequence, weights: str | None = None) -> float:
    """1 - observed disagreement / disagreement expected by chance. NaN when undefined
    (both labellers always gave the same single label)."""
    if len(a) != len(b) or not a:
        raise ValueError("need two non-empty lists of the same length")
    n = len(a)
    labels = sorted(set(a) | set(b))
    pairs = Counter(zip(a, b, strict=True))
    count_a, count_b = Counter(a), Counter(b)
    observed = expected = 0.0
    for i in labels:
        for j in labels:
            w = _weight(i, j, weights)
            observed += w * pairs[(i, j)] / n
            expected += w * (count_a[i] / n) * (count_b[j] / n)
    return math.nan if expected == 0 else 1 - observed / expected


def _weight(i, j, weights: str | None) -> float:
    if weights is None:
        return 0.0 if i == j else 1.0
    if weights == "quadratic":
        return float((i - j) ** 2)
    raise ValueError(f"unknown weights: {weights!r}")


def percent_agreement(a: Sequence, b: Sequence) -> float:
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a)
