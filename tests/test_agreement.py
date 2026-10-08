import math

import pytest
from sklearn.metrics import cohen_kappa_score

from tutor_eval.agreement import cohen_kappa, percent_agreement


def test_perfect_agreement_is_one():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0


def test_textbook_example():
    # 2x2 table: 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no -> po = 0.7, pe = 0.5, kappa = 0.4
    a = [1] * 25 + [0] * 25
    b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
    assert cohen_kappa(a, b) == pytest.approx(0.4)
    assert percent_agreement(a, b) == pytest.approx(0.7)


@pytest.mark.parametrize("weights", [None, "quadratic"])
def test_matches_scikit_learn(weights):
    a = [5, 4, 4, 3, 5, 2, 1, 4, 5, 3]
    b = [5, 5, 4, 3, 4, 2, 2, 4, 5, 1]
    assert cohen_kappa(a, b, weights) == pytest.approx(cohen_kappa_score(a, b, weights=weights))


def test_undefined_when_both_always_say_the_same():
    assert math.isnan(cohen_kappa([1, 1, 1], [1, 1, 1]))


def test_lengths_must_match():
    with pytest.raises(ValueError):
        cohen_kappa([1, 0], [1])
