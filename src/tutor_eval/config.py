"""Settings: API key, model IDs and budget limits.

Values are read from `Portfolio Projects/.env` (two folders above this repo), then
from a local `repo/.env` (for a fresh clone), then from ordinary environment
variables. A variable already set in the shell always wins.
The API key is never printed: `Settings` hides it from repr().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_ENV_FILE = REPO_ROOT.parent.parent / ".env"  # Portfolio Projects/.env
LOCAL_ENV_FILE = REPO_ROOT / ".env"
DATA_DIR = REPO_ROOT / "data"
EVALS_DIR = REPO_ROOT / "evals"
RESULTS_DIR = EVALS_DIR / "results"

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class Settings:
    api_key: str | None = field(repr=False)
    base_url: str
    model_main: str | None
    model_cheap: str | None
    model_judge: str | None
    reasoning_effort: str
    max_cost_per_run_usd: float
    project_budget_usd: float


def load_settings() -> Settings:
    load_dotenv(SHARED_ENV_FILE, override=False)
    load_dotenv(LOCAL_ENV_FILE, override=False)
    return Settings(
        api_key=_get("OPENROUTER_API_KEY"),
        base_url=_get("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL,
        model_main=_get("MODEL_MAIN"),
        model_cheap=_get("MODEL_CHEAP"),
        model_judge=_get("MODEL_JUDGE"),
        # Reasoning models spend max_tokens on hidden thinking first; "low" keeps
        # short answers and judge JSON from being cut off (a lesson from earlier projects).
        reasoning_effort=_get("REASONING_EFFORT") or "low",
        max_cost_per_run_usd=float(_get("MAX_COST_PER_RUN_USD") or 3),
        # This project's own budget (US$2 in the build brief), checked against the traces.
        project_budget_usd=float(_get("TUTOR_EVAL_BUDGET_USD") or 2),
    )


def _get(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def resolve_model(name: str, settings: Settings) -> str:
    """Turn an alias ("main", "cheap", "judge") into a model ID.

    Anything containing "/" is used as a full OpenRouter ID, e.g. "anthropic/claude-haiku-5.5".
    """
    aliases = {"main": settings.model_main, "cheap": settings.model_cheap, "judge": settings.model_judge}
    if name in aliases:
        if not aliases[name]:
            raise ValueError(f"MODEL_{name.upper()} is not set in .env")
        return aliases[name]
    if "/" not in name:
        raise ValueError(f"'{name}' is not an alias (main, cheap, judge) or an OpenRouter ID (provider/model)")
    return name


def model_family(model_id: str) -> str:
    """"anthropic/claude-haiku-5.5" -> "anthropic". The judge must not share a family with a tested model,
    because judges tend to prefer answers written in their own style."""
    return model_id.split("/", 1)[0].lstrip("~").lower()
