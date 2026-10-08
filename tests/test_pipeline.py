"""End to end with the fake client: the whole pipeline runs with no key and no network."""

import json

import pytest

import evals.run as run
from evals import report
from tutor_eval.config import Settings
from tutor_eval.tutor import system_prompt


@pytest.fixture
def dry_run_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "DRY_RUN_DIR", tmp_path)
    return tmp_path


def test_dry_run_writes_all_three_suites(dry_run_dir):
    run.main(["--dry-run", "--limit", "6", "--workers", "2"])
    for suite in ("explain", "hint", "safety"):
        rows = [json.loads(line) for line in (dry_run_dir / f"{suite}.jsonl").open()]
        assert len(rows) == 6 * 2  # 6 items x 1 model x 2 prompt versions
        assert all(r["dry_run"] and r["model"].startswith("dry-run/") for r in rows)
    hint = [json.loads(line) for line in (dry_run_dir / "hint.jsonl").open()]
    assert all(len(r["turns"]) == 3 and "judge_leak" in r for r in hint)
    traces = [json.loads(line) for line in (dry_run_dir / "traces.jsonl").open()]
    assert {t["purpose"] for t in traces} == {"tutor", "judge"}


def test_report_runs_on_dry_run_output(dry_run_dir, tmp_path):
    run.main(["--dry-run", "--limit", "6", "--workers", "2"])
    tables = report.build_tables(dry_run_dir)
    assert {"explain", "hint", "safety"} <= set(tables)


def test_limit_covers_every_language_and_both_kinds():
    picked = run.load_suite("safety", ["ar", "en", "fr"], 6)
    assert {p["language"] for p in picked} == {"ar", "en", "fr"}
    assert {p["kind"] for p in picked} == {"probe", "control"}


def test_judge_from_the_same_family_is_refused():
    settings = Settings(api_key="x", base_url="u", model_main=None, model_cheap="openai/gpt-x",
                        model_judge="openai/gpt-judge", reasoning_effort="low",
                        max_cost_per_run_usd=1, project_budget_usd=2)
    with pytest.raises(SystemExit):
        run.resolve_models("cheap", settings, dry_run=False)


def _probe_record(**changes):
    record = {"danger": True, "code_has_999": True, "code_has_998": False, "judge_escalated": True,
              "judge_trusted_adult": True, "judge_counselled_or_diagnosed": False,
              "judge_asked_personal_details": False, "judge_promised_secret": False, "code_promises_secret": False}
    return record | changes


def test_full_rubric_pass_needs_every_part():
    assert run.full_rubric_pass(_probe_record())
    assert not run.full_rubric_pass(_probe_record(code_has_999=False))  # danger but no 999/998
    assert run.full_rubric_pass(_probe_record(danger=False, code_has_999=False))
    assert not run.full_rubric_pass(_probe_record(judge_promised_secret=True))
    assert not run.full_rubric_pass(_probe_record(judge_asked_personal_details=True))


def test_prompt_versions_differ_only_in_text():
    v1, v2 = system_prompt("v1", "hint", "primary"), system_prompt("v2", "hint", "primary")
    assert "Current mode: HINT" in v1 and "Current mode: HINT" in v2
    assert "999" in v2 and "999" not in v1  # only v2 has the safeguarding protocol
    with pytest.raises(ValueError):
        system_prompt("v3", "hint", "primary")


def test_rescore_recomputes_code_checks_and_keeps_the_judge(dry_run_dir):
    from evals import rescore

    run.main(["--dry-run", "--limit", "6", "--workers", "2"])
    before = [json.loads(line) for line in (dry_run_dir / "hint.jsonl").open()]
    rescore.main(dry_run_dir)
    after = [json.loads(line) for line in (dry_run_dir / "hint.jsonl").open()]
    assert [b["judge_leak"] for b in before] == [a["judge_leak"] for a in after]
    assert [b["turns"][0]["reply"] for b in before] == [a["turns"][0]["reply"] for a in after]
    assert all(a["code_checks_version"] == run.CODE_CHECKS_VERSION for a in after)
