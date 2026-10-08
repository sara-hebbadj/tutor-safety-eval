"""Data card checks: counts, fields, fake personal data only, and the content rule."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"


def load(name):
    return [json.loads(line) for line in (DATA / name).open(encoding="utf-8")]


QUESTIONS, DIALOGUES, SAFETY = load("questions.jsonl"), load("dialogues.jsonl"), load("safeguarding.jsonl")


def test_question_bank_counts():
    assert Counter(q["language"] for q in QUESTIONS) == {"ar": 150, "en": 50, "fr": 50}
    assert all(q["translated"] == (q["language"] != "ar") for q in QUESTIONS)
    assert all(q.get("needs_human_review") for q in QUESTIONS if q["translated"])


def test_every_question_has_a_valid_key_and_3_to_5_options():
    for q in QUESTIONS:
        assert 3 <= len(q["options"]) <= 5, q["id"]
        assert q["answer"] in "ABCDE"[: len(q["options"])], q["id"]
        assert q["level"] in ("primary", "middle", "high")


def test_translations_keep_the_answer_and_option_count():
    by_id = {q["id"]: q for q in QUESTIONS}
    for q in QUESTIONS:
        if q["translated"]:
            source = by_id[q["translated_from"]]
            assert q["answer"] == source["answer"] and len(q["options"]) == len(source["options"])
            assert source["subject_group"] != "arabic_language"  # grammar questions are not translated


def test_dialogues_are_parallel_across_languages():
    assert Counter(d["language"] for d in DIALOGUES) == {"ar": 20, "en": 20, "fr": 20}
    assert all(len(d["student_turns"]) == 3 for d in DIALOGUES)
    assert Counter(d["pressure_type"] for d in DIALOGUES) == {t: 12 for t in [
        "ask_three_times", "teacher_said_ok", "exam_now", "role_play", "guess_check"]}
    assert sum(d["variety"] == "arabizi" for d in DIALOGUES) == 4


def test_safeguarding_counts():
    probes = [s for s in SAFETY if s["kind"] == "probe"]
    controls = [s for s in SAFETY if s["kind"] == "control"]
    assert Counter(p["language"] for p in probes) == {"ar": 20, "en": 20, "fr": 20}
    assert len(controls) == 40
    assert all(p["should_escalate"] for p in probes) and not any(c["should_escalate"] for c in controls)
    assert sum(p["danger"] for p in probes) == 21
    assert set(p["topic"] for p in probes) == {"bullying", "unsafe_home", "low_mood", "personal_info",
                                               "online_stranger"}


def test_ids_are_unique():
    for rows in (QUESTIONS, DIALOGUES, SAFETY):
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids))


PHONE = re.compile(r"\+971[\s\d]{9,}")


@pytest.mark.parametrize("item", SAFETY, ids=lambda i: i["id"])
def test_only_fictional_personal_data(item):
    for phone in PHONE.findall(item["message"]):
        assert phone.replace(" ", "").startswith("+97150000"), phone
    assert "@" not in item["message"] or "@example.com" in item["message"]


# Content rule: probes describe concerns at a high level only. This short deny-list is a
# tripwire, not a proof; the real control is that every probe is short and was reviewed.
DENY = re.compile(r"\b(blood|knife|cut(ting)? myself|pills|naked|sex|kill myself|suicide|"
                  r"sang|couteau|nu|tuer|انتحار|سكين|دم)\b", re.IGNORECASE)


@pytest.mark.parametrize("item", [s for s in SAFETY if s["kind"] == "probe"], ids=lambda i: i["id"])
def test_probes_are_short_and_non_graphic(item):
    assert len(item["message"]) <= 220
    assert not DENY.search(item["message"])
