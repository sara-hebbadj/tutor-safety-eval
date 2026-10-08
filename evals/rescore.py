"""Re-apply the CODE checks to replies that are already saved (no model calls, no cost).

    python -m evals.rescore                 # rewrites evals/results/{explain,hint,safety}.jsonl in place

Used once on 8 October 2026, after the first live run exposed two bugs in the code checks
(see README, "What failed and what I changed"). Replies, judge verdicts, costs and run IDs are
not touched; only code-check fields and the scores that combine code and judge are recomputed,
and each line gets the current `code_checks_version`.
"""

from __future__ import annotations

import json
from pathlib import Path

from evals.run import (
    CODE_CHECKS_VERSION,
    combined_scores,
    explain_checks,
    hint_summary,
    load_jsonl,
    safety_checks,
    turn_checks,
)
from tutor_eval.config import DATA_DIR, RESULTS_DIR

ITEM_FILES = {"explain": "questions.jsonl", "hint": "dialogues.jsonl", "safety": "safeguarding.jsonl"}


def rescore_record(record: dict, item: dict) -> dict:
    suite = record["suite"]
    if suite == "explain":
        record |= explain_checks(record["reply"], item)
    elif suite == "hint":
        record["turns"] = [t | turn_checks(t["reply"], item) for t in record["turns"]]
        record |= hint_summary(record["turns"])
    else:
        record |= safety_checks(record["reply"], item)
    record["code_checks_version"] = CODE_CHECKS_VERSION
    return record | combined_scores(record)


def rescore_file(path: Path, suite: str) -> int:
    items = {i["id"]: i for i in load_jsonl(DATA_DIR / ITEM_FILES[suite])}
    records = [rescore_record(r, items[r["item_id"]]) for r in load_jsonl(path)]
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records)


def main(results_dir: Path = RESULTS_DIR) -> None:
    for suite in ITEM_FILES:
        path = results_dir / f"{suite}.jsonl"
        if path.exists():
            print(f"{suite}: re-scored {rescore_file(path, suite)} lines")


if __name__ == "__main__":
    main()
