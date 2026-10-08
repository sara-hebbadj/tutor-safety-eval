"""Build the question bank: 150 Arabic school questions from ArabicMMLU, 50 of them
also in English and French (machine-translated, flagged for human review).

    python data/build_questions.py              # sample the 150 Arabic questions (no key needed)
    python data/build_questions.py --translate  # also translate 50 (needs a key; about US$0.05)

Source: ArabicMMLU (MBZUAI), CC BY-NC 4.0, test split, pinned to one dataset revision.
The derived file data/questions.jsonl keeps that licence (attribution, non-commercial).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutor_eval.config import DATA_DIR, RESULTS_DIR, load_settings  # noqa: E402
from tutor_eval.judge import parse_json_object  # noqa: E402
from tutor_eval.llm_client import TRANSLATE_HEADING, OpenRouterClient  # noqa: E402

REVISION = "7aa530e2893ac420352b3f5c1a1310c010e9758b"  # ArabicMMLU commit used on 8 Oct 2026
SOURCE_URL = f"https://huggingface.co/datasets/MBZUAI/ArabicMMLU/resolve/{REVISION}/All/test.csv"
RAW_FILE = DATA_DIR / "raw" / "ArabicMMLU_All_test.csv"
OUT_FILE = DATA_DIR / "questions.jsonl"
SEED = 42
# Not a model under test and not the judge, so neither gains from its own wording.
TRANSLATOR_MODEL = "deepseek/deepseek-v4.1-flash"

# (subject group, level, ArabicMMLU subjects, how many). ArabicMMLU has no middle- or
# high-school maths, so high-school physics stands in for quantitative questions.
CELLS = [
    ("maths_physics", "primary", ["Math"], 25),
    ("maths_physics", "high", ["Physics"], 13),
    ("science", "primary", ["Natural Science"], 13),
    ("science", "middle", ["Natural Science"], 13),
    ("science", "high", ["Biology"], 12),
    ("arabic_language", "primary", ["Arabic Language"], 13),
    ("arabic_language", "middle", ["Arabic Language"], 12),
    ("arabic_language", "high", ["Arabic Language"], 12),
    ("social_studies", "primary", ["Social Science"], 13),
    ("social_studies", "middle", ["Social Science"], 12),
    ("social_studies", "high", ["History", "Geography"], 12),
]
N_TRANSLATED = 50
# Questions that need a picture, a table or underlined words cannot be answered from text.
NEEDS_FIGURE = re.compile("الشكل|الصورة|المجاور|الرسم|الجدول|الخريطة|تحتها خط|تحته خط")
OPTION_COLUMNS = [f"Option {i}" for i in range(1, 6)]


def load_raw() -> pd.DataFrame:
    if not RAW_FILE.exists():
        RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading ArabicMMLU test split ({REVISION[:7]}) ...")
        urllib.request.urlretrieve(SOURCE_URL, RAW_FILE)
    return pd.read_csv(RAW_FILE)


def usable(df: pd.DataFrame) -> pd.DataFrame:
    df = df[(df["is_few_shot"] == 0) & df["Context"].isna()]
    df = df[df[OPTION_COLUMNS].notna().sum(axis=1) >= 3]  # at least 3 options
    df = df[df["Question"].str.len() <= 300]
    return df[~df["Question"].str.contains(NEEDS_FIGURE)]


def sample_arabic(df: pd.DataFrame) -> list[dict]:
    items = []
    for group, level, subjects, n in CELLS:
        cell = df[df["Subject"].isin(subjects) & (df["Level"] == level.capitalize())]
        for _, row in cell.sample(n=n, random_state=SEED).iterrows():
            options = [str(row[c]).strip() for c in OPTION_COLUMNS if pd.notna(row[c])]
            items.append({
                "id": f"q{len(items) + 1:03d}", "language": "ar", "subject_group": group, "level": level,
                "subject": row["Subject"], "country": row["Country"] if pd.notna(row["Country"]) else "",
                "question": str(row["Question"]).strip(), "options": options, "answer": row["Answer Key"],
                "source": "ArabicMMLU", "source_id": int(row["ID"]), "translated": False,
            })
    return items


def pick_for_translation(items: list[dict]) -> list[dict]:
    """Round-robin over the non-Arabic-language cells (grammar questions do not translate)."""
    queues = {}
    for item in items:
        if item["subject_group"] != "arabic_language":
            queues.setdefault((item["subject_group"], item["level"]), []).append(item)
    picked = []
    while len(picked) < N_TRANSLATED:
        for queue in queues.values():
            if queue and len(picked) < N_TRANSLATED:
                picked.append(queue.pop(0))
    return sorted(picked, key=lambda i: i["id"])


def translation_messages(item: dict) -> list[dict]:
    system = (
        f"{TRANSLATE_HEADING}\n\nTranslate this Arabic school multiple-choice question into English and into "
        "French, for students of the same age. Keep the meaning, numbers, units and the ORDER of the options "
        "exactly. Do not mark or hint at the answer and do not add explanations. Return ONLY JSON: "
        '{"en": {"question": "...", "options": ["...", "..."]}, "fr": {"question": "...", "options": ["..."]}}'
    )
    user = json.dumps({"question": item["question"], "options": item["options"]}, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def translate(items: list[dict]) -> list[dict]:
    client = OpenRouterClient(load_settings())
    traces = RESULTS_DIR / "traces_translation.jsonl"
    traces.parent.mkdir(parents=True, exist_ok=True)
    translated = []
    for item in pick_for_translation(items):
        for attempt in range(2):
            response = client.chat(TRANSLATOR_MODEL, translation_messages(item), max_tokens=1500,
                                   json_mode=True, effort="none")
            with traces.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"purpose": "translate", "model": TRANSLATOR_MODEL, "item_id": item["id"],
                                    "outcome": "ok", "cost_usd": response.cost_usd,
                                    "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                                    "latency_s": response.latency_s}) + "\n")
            try:
                data = parse_json_object(response.text)
                if all(len(data[lang]["options"]) == len(item["options"]) for lang in ("en", "fr")):
                    break
            except (ValueError, KeyError, TypeError):
                pass
            if attempt == 1:
                raise SystemExit(f"Translation failed twice for {item['id']}; stopping.")
        for lang in ("en", "fr"):
            translated.append(item | {
                "id": f"{item['id']}-{lang}", "language": lang, "question": data[lang]["question"].strip(),
                "options": [str(o).strip() for o in data[lang]["options"]], "translated": True,
                "translated_from": item["id"], "translation_model": TRANSLATOR_MODEL, "needs_human_review": True,
            })
        print(f"translated {item['id']}")
    return translated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--translate", action="store_true", help="also translate 50 questions (needs a key)")
    args = parser.parse_args()
    random.seed(SEED)
    items = sample_arabic(usable(load_raw()))
    if args.translate:
        items += translate(items)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"wrote {len(items)} questions to {OUT_FILE.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
