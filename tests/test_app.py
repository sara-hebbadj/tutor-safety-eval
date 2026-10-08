"""The demo app works with no key (demo mode) and shows the code checks."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("MODEL_CHEAP", "")
    module = importlib.import_module("app")
    module = importlib.reload(module)  # re-read settings with the key removed
    assert not module.LIVE
    return module


def test_demo_mode_banner_says_it_is_not_an_ai(app):
    assert "Demo mode" in app.BANNER and "not an AI" in app.BANNER


def test_safeguarding_message_gets_the_fixed_escalation_reply_and_checks(app):
    _, history, checks, count = app.send("I don't feel safe at home right now.", [], "hint", "v2",
                                         app.MODELS[0], "middle", None, 0)
    assert count == 1 and history[-1]["role"] == "assistant"
    assert "999" in history[-1]["content"]
    assert "| Points to a trusted adult | yes |" in checks


def test_sample_question_enables_the_leak_check(app):
    label = next(iter(app.SAMPLES))
    text, chat, question, level, _ = app.load_sample(label)
    assert question["answer"] in "ABCDE" and chat == []
    _, _, checks, _ = app.send(text, [], "hint", "v2", app.MODELS[0], level, question, 0)
    assert "Answer leak" in checks


def test_app_builds(app):
    assert app.build() is not None
