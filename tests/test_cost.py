import json

import pytest

from tutor_eval.cost import BudgetExceeded, CostGuard, average_cost_per_call, estimate_run, spent_so_far


def test_guard_stops_at_the_limit():
    guard = CostGuard(0.01)
    guard.add(0.006)
    with pytest.raises(BudgetExceeded):
        guard.add(0.006)


def test_spend_and_averages_come_from_all_trace_files(tmp_path):
    (tmp_path / "smoke").mkdir()
    rows = [{"model": "m/a", "purpose": "tutor", "outcome": "ok", "cost_usd": 0.001},
            {"model": "m/a", "purpose": "tutor", "outcome": "ok", "cost_usd": 0.003}]
    (tmp_path / "smoke" / "traces.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (tmp_path / "traces_translation.jsonl").write_text(json.dumps(
        {"model": "m/t", "purpose": "translate", "outcome": "ok", "cost_usd": 0.01}))
    assert spent_so_far(tmp_path) == pytest.approx(0.014)
    assert average_cost_per_call(tmp_path)[("m/a", "tutor")] == pytest.approx(0.002)


def test_estimate_uses_history_with_margin_else_worst_case():
    history = {("m/a", "tutor"): 0.001}
    prices = {"m/b": (1.0, 2.0)}
    estimate = estimate_run([("m/a", "tutor", 500, 1000), ("m/b", "judge", 1_000_000, 0)], history, prices)
    assert estimate == pytest.approx(0.001 * 1.3 + 1.0)
