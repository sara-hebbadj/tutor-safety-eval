# Notes for coding agents working on this repo

Project P13 of Sara Hebbadj's portfolio: a safety and teaching evaluation of an AI homework tutor for a
fictional Dubai edtech company, "Madrasa Plus". Sara must be able to explain every line, so keep functions
short and names plain.

## Layout

- `src/tutor_eval/tutor.py` + `prompts/tutor_v*.md`: the system under test. A change to a tutor prompt is a
  new prompt version (v3), never an edit of v1/v2, or earlier results stop meaning anything.
- `src/tutor_eval/checks.py`: code checks. If you fix a blind spot, keep a test for the old failure.
- `src/tutor_eval/judge.py` + `prompts/judge_*.md`: the AI judge. Its definitions must match `docs/rubric.md`
  (Sara labels with the rubric).
- `src/tutor_eval/llm_client.py`: the only place that calls a model. Every call asks for low reasoning effort
  (`REASONING_EFFORT`); translation turns reasoning off.
- `evals/run.py`, `evals/report.py`, `evals/labels.py`: runner, tables/charts, human-label sheet and kappa.
- `data/build_questions.py`, `data/build_sets.py`: rebuild the test sets. Do not edit the `.jsonl` files by
  hand.

## Rules

- **Content rule for safeguarding data:** probes stay short and non-graphic, stated at a high level. Never
  write graphic, sexual or otherwise harmful content involving minors, and never instructions for self-harm.
  If a model output contains such content, store it redacted.
- Tests never touch the network (a fixture blocks sockets) and need no key. Use `FakeClient`.
- Real results go in `evals/results/`; fake ones in `evals/dry_run/` (git-ignored). Never copy a dry-run
  number anywhere.
- Changing a test set or a go/no-go threshold after a run must be said in the README and RESULTS.md, with
  both runs reported.
- Keys come from `Portfolio Projects/.env` or environment variables. Never print or commit them
  (`grep -r "sk-or-" .` must find nothing).
- Budget: `TUTOR_EVAL_BUDGET_USD` (default 2) is checked against all traces before a run.
- Ask Sara before creating a GitHub repo, pushing, deploying a Space or publishing a dataset.

## Checks before you finish

```bash
pytest -q
ruff check .
python -m evals.run --dry-run --limit 6   # pipeline still works end to end (fake client)
```
