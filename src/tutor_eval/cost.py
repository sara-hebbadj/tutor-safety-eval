"""Budget protection: an estimate before a run and a guard during it.

1. Before: estimate the run from the average real cost per call seen in earlier runs
   (the smoke run), with a 30% margin. A model or purpose never run before is priced
   at the worst case (every call uses its full max_tokens at the listed price).
2. During: `CostGuard` adds up the real cost of each call (OpenRouter `usage.cost`) and
   stops the run as soon as the total passes the limit.
"""

from __future__ import annotations

import csv
import json
import threading
from collections import defaultdict
from pathlib import Path

SAFETY_MARGIN = 1.3
FALLBACK_PRICE = (15.0, 75.0)  # US$ per million tokens: deliberately expensive for unknown models


class BudgetExceeded(RuntimeError):
    pass


def load_prices(path: Path) -> dict[str, tuple[float, float]]:
    """model_id -> (input, output) US$ per million tokens, from evals/model_prices.csv."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        return {r["model_id"]: (float(r["input_usd_per_mtok"]), float(r["output_usd_per_mtok"])) for r in rows}


def worst_case_cost(model: str, input_tokens: int, max_output_tokens: int, prices: dict) -> float:
    price_in, price_out = prices.get(model, FALLBACK_PRICE)
    return (input_tokens * price_in + max_output_tokens * price_out) / 1_000_000


def read_traces(results_dir: Path) -> list[dict]:
    """Every trace line under evals/results/ (smoke runs, full runs and translation)."""
    records = []
    for path in sorted(results_dir.rglob("traces*.jsonl")):
        with path.open(encoding="utf-8") as f:
            records += [json.loads(line) for line in f if line.strip()]
    return records


def spent_so_far(results_dir: Path) -> float:
    return sum(r.get("cost_usd") or 0.0 for r in read_traces(results_dir))


def average_cost_per_call(results_dir: Path) -> dict[tuple[str, str], float]:
    """(model, purpose) -> mean real cost of one call, from earlier runs."""
    totals: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in read_traces(results_dir):
        if r.get("outcome") == "ok":
            totals[(r["model"], r["purpose"])].append(r.get("cost_usd") or 0.0)
    return {key: sum(v) / len(v) for key, v in totals.items()}


def estimate_run(planned: list[tuple[str, str, int, int]], history: dict, prices: dict) -> float:
    """planned: one (model, purpose, input_tokens, max_output_tokens) per call."""
    total = 0.0
    for model, purpose, tokens_in, max_out in planned:
        if (model, purpose) in history:
            total += history[(model, purpose)] * SAFETY_MARGIN
        else:
            total += worst_case_cost(model, tokens_in, max_out, prices)
    return total


class CostGuard:
    """Running total during a run (thread-safe); raises BudgetExceeded at the limit."""

    def __init__(self, limit_usd: float):
        self.limit_usd = limit_usd
        self.spent_usd = 0.0
        self._lock = threading.Lock()

    def add(self, cost_usd: float) -> None:
        with self._lock:
            self.spent_usd += cost_usd
            if self.spent_usd > self.limit_usd:
                raise BudgetExceeded(f"Run stopped: spent ${self.spent_usd:.4f}, limit ${self.limit_usd:.4f}.")
