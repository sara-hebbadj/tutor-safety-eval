import pandas as pd
import pytest

from evals import labels


def test_score_computes_kappa_per_criterion(tmp_path, monkeypatch):
    monkeypatch.setattr(labels, "LABELS_DIR", tmp_path)
    monkeypatch.setattr(labels, "SHEET", tmp_path / "sheet.csv")
    monkeypatch.setattr(labels, "KEY", tmp_path / "key.csv")
    sheet = pd.DataFrame({"label_id": ["L1", "L2", "L3", "L4"],
                          "human_leak": ["yes", "no", "yes", "no"], "human_scaffolding": [5, 3, 2, ""]})
    for column in ["escalated", "trusted_adult", "promised_secret", "asked_personal_details", "age_fit", "language"]:
        sheet[f"human_{column}"] = ""
    key = pd.DataFrame({"label_id": ["L1", "L2", "L3", "L4"], "judge_leak": [True, False, False, False],
                        "judge_scaffolding": [5, 3, 2, 4]})
    for column in ["escalated", "trusted_adult", "promised_secret", "asked_personal_details", "age_fit", "language"]:
        key[f"judge_{column}"] = None
    sheet.to_csv(labels.SHEET, index=False)
    key.to_csv(labels.KEY, index=False)
    table = labels.score().set_index("criterion")
    assert table.loc["leak", "n"] == 4 and table.loc["leak", "agreement"] == pytest.approx(0.75)
    assert table.loc["scaffolding", "n"] == 3 and table.loc["scaffolding", "kappa"] == pytest.approx(1.0)
    assert table.loc["escalated", "n"] == 0
