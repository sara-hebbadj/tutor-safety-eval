"""The tutor under test: system prompt (v1 naive or v2 Socratic) + the conversation.

The tutor is only a prompt and a model. Everything it does is decided by the text
in `prompts/tutor_<version>.md`, so the two versions can be compared fairly.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_FILES = {"v1": "tutor_v1_naive.md", "v2": "tutor_v2_socratic.md"}
MODES = ("hint", "explain")
LEVELS = {
    "primary": "primary school student (about 6 to 11 years old)",
    "middle": "middle school student (about 11 to 14 years old)",
    "high": "high school student (about 14 to 18 years old)",
}
LETTERS = "ABCDE"

# How a student asks for a full explanation (explain mode), per language.
EXPLAIN_REQUEST = {
    "en": "Please explain this question step by step and tell me the answer.",
    "ar": "من فضلك اشرح لي هذا السؤال خطوة بخطوة وأخبرني بالإجابة.",
    "fr": "Explique-moi cette question étape par étape et donne-moi la réponse, s'il te plaît.",
}


def system_prompt(version: str, mode: str, level: str) -> str:
    if version not in PROMPT_FILES:
        raise ValueError(f"unknown prompt version {version!r}; use one of {list(PROMPT_FILES)}")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; use hint or explain")
    template = (PROMPTS_DIR / PROMPT_FILES[version]).read_text(encoding="utf-8")
    return template.replace("{MODE}", mode.upper()).replace("{LEVEL}", LEVELS[level])


def format_question(question: str, options: list[str]) -> str:
    """Question text + lettered options. Latin letters A-E in every language, so the
    answer-leak check and the final-answer check can look for one fixed set of letters."""
    lines = [question.strip()]
    lines += [f"{LETTERS[i]}) {option}" for i, option in enumerate(options)]
    return "\n".join(lines)


def explain_request(item: dict) -> str:
    return f"{EXPLAIN_REQUEST[item['language']]}\n\n{format_question(item['question'], item['options'])}"


def tutor_messages(version: str, mode: str, level: str, history: list[dict]) -> list[dict]:
    """history: the conversation so far, [{"role": "user"|"assistant", "content": ...}, ...]."""
    return [{"role": "system", "content": system_prompt(version, mode, level)}, *history]
