"""Sara's labels: check the AI judge against a human, criterion by criterion.

    python -m evals.labels make    # writes evals/labels/human_labels.csv (80 items, no judge verdicts)
    python -m evals.labels score   # after Sara fills the human_* columns: kappa per criterion

The sheet hides the model name and the judge's verdicts so the labels are blind. The verdicts
live in evals/labels/judge_key.csv: do not open it before labelling.
"""

from __future__ import annotations

import argparse

import pandas as pd

from evals.report import load_latest
from tutor_eval.agreement import cohen_kappa, percent_agreement
from tutor_eval.config import EVALS_DIR, RESULTS_DIR
from tutor_eval.tutor import format_question

LABELS_DIR = EVALS_DIR / "labels"
SHEET, KEY = LABELS_DIR / "human_labels.csv", LABELS_DIR / "judge_key.csv"
SEED = 42
PER_SYSTEM = {"hint": 10, "safety_probe": 6, "safety_control": 4}  # x 4 tutors = 80 items
YES_NO = ["leak", "escalated", "trusted_adult", "promised_secret", "asked_personal_details"]
SCORES = ["scaffolding", "age_fit", "language"]


def _sample(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """n rows per tutor, spread over languages (round-robin after a seeded shuffle)."""
    picked = []
    for _system, group in df.groupby("system"):
        shuffled = group.sample(frac=1, random_state=SEED)
        shuffled = shuffled.assign(rank=shuffled.groupby("language").cumcount()).sort_values(["rank", "language"])
        picked.append(shuffled.head(n))
    return pd.concat(picked)


def _transcript(row) -> str:
    lines = []
    for turn, student in zip(row["turns"], row["student_turns"], strict=False):
        lines += [f"STUDENT: {student}", f"TUTOR (turn {turn['turn']}): {turn['reply']}"]
    return "\n\n".join(lines)


def make() -> None:
    hint = load_latest(RESULTS_DIR, "hint")
    safety = load_latest(RESULTS_DIR, "safety")
    dialogues = pd.read_json(EVALS_DIR.parent / "data" / "dialogues.jsonl", lines=True).set_index("id")
    hint = hint[hint["judge_error"].fillna("") == ""].join(dialogues[["student_turns", "question", "options"]],
                                                           on="item_id")
    safety = safety[safety["judge_error"].fillna("") == ""]
    messages = pd.read_json(EVALS_DIR.parent / "data" / "safeguarding.jsonl", lines=True).set_index("id")["message"]
    chosen = pd.concat([
        _sample(hint, PER_SYSTEM["hint"]),
        _sample(safety[safety["kind"] == "probe"], PER_SYSTEM["safety_probe"]),
        _sample(safety[safety["kind"] == "control"], PER_SYSTEM["safety_control"]),
    ]).sample(frac=1, random_state=SEED).reset_index(drop=True)  # mix the order

    sheet, key = [], []
    for n, row in chosen.iterrows():
        label_id = f"L{n + 1:02d}"
        is_hint = row["suite"] == "hint"
        sheet.append({
            "label_id": label_id, "task": "hint dialogue" if is_hint else "safety reply",
            "language": row["language"], "student_level": row["level"],
            "question_and_correct_answer": (f"{format_question(row['question'], row['options'])}\n"
                                            f"CORRECT: {row['answer']}") if is_hint else "",
            "conversation": _transcript(row) if is_hint else
            f"STUDENT: {messages[row['item_id']]}\n\nTUTOR: {row['reply']}",
            **{f"human_{c}": "" for c in YES_NO + SCORES}, "human_notes": "",
        })
        key.append({"label_id": label_id, "suite": row["suite"], "model": row["model"],
                    "prompt_version": row["prompt_version"], "item_id": row["item_id"],
                    **{f"judge_{c}": row.get(f"judge_{c}") for c in YES_NO + SCORES}})
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sheet).to_csv(SHEET, index=False, encoding="utf-8-sig")  # -sig: Excel opens Arabic correctly
    pd.DataFrame(key).to_csv(KEY, index=False)
    print(f"wrote {len(sheet)} items to {SHEET} (and the hidden judge key to {KEY})")


def _to_bool(value) -> bool | None:
    text = str(value).strip().lower()
    return {"yes": True, "y": True, "true": True, "1": True, "no": False, "n": False, "false": False,
            "0": False}.get(text)


def _to_score(value) -> int | None:
    """1-5 from "4", 4 or 4.0 (spreadsheets often save whole numbers as 4.0); anything else -> None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number in (1, 2, 3, 4, 5) else None


def score() -> pd.DataFrame:
    merged = pd.read_csv(SHEET, encoding="utf-8-sig").merge(pd.read_csv(KEY), on="label_id")
    rows = []
    for criterion in YES_NO + SCORES:
        human = merged[f"human_{criterion}"]
        judge = merged[f"judge_{criterion}"]
        convert = _to_bool if criterion in YES_NO else _to_score
        pairs = [(convert(h), convert(j)) for h, j in zip(human, judge, strict=True)]
        pairs = [(h, j) for h, j in pairs if h is not None and j is not None]
        if len(pairs) < 2:
            rows.append({"criterion": criterion, "n": len(pairs), "agreement": None, "kappa": None})
            continue
        h, j = zip(*pairs, strict=True)
        kappa = cohen_kappa(h, j, None if criterion in YES_NO else "quadratic")
        rows.append({"criterion": criterion, "n": len(pairs), "agreement": round(percent_agreement(h, j), 3),
                     "kappa": round(kappa, 3), "kappa_type": "plain" if criterion in YES_NO else "quadratic"})
    table = pd.DataFrame(rows)
    table.to_csv(LABELS_DIR / "agreement.csv", index=False)
    print(table.to_string(index=False))
    if table["n"].max() == 0:
        print("\nNo human labels yet: fill the human_* columns in", SHEET)
    return table


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("command", choices=["make", "score"])
    args = parser.parse_args(argv)
    if args.command == "make":
        make()
    else:
        score()


if __name__ == "__main__":
    main()
