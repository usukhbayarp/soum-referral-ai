import copy
import json
from pathlib import Path
import pytest
from scripts.dataset import validate_cases, export_cases
from app.core import Contract


def empty():
    return {f["id"]: [] for f in Contract("provisional-0.1").fields}


def record(case="a", underlying="a", split="train", review="reviewed"):
    labels = empty()
    labels["allergies"] = [1]
    return {
        "case_id": case,
        "underlying_case_id": underlying,
        "source_note": f"{case}: Харшилгүй.",
        "expected_assignments": labels,
        "schema_version": "provisional-0.1",
        "segmentation_version": "sentence-lines-1",
        "split": split,
        "synthetic_origin": "fictional unit test only",
        "clinician_review_status": review,
    }


def test_export_excludes_unreviewed_rejected_test(tmp_path):
    records = [
        record(),
        record("b", "b", "development"),
        record("c", "c", "test"),
        record("d", "d", "train", "unreviewed"),
        record("e", "e", "train", "rejected"),
    ]
    target = tmp_path / "export"
    assert export_cases(validate_cases(records), target) == 2
    assert not (target / "test.jsonl").exists()
    train = json.loads((target / "train.jsonl").read_text())
    assert [m["role"] for m in train["messages"]] == ["system", "user", "assistant"]
    assert json.loads(train["messages"][-1]["content"])["allergies"] == [1]
    assert "source_units" in train["messages"][1]["content"]


def test_split_leakage():
    with pytest.raises(ValueError, match="overlap"):
        validate_cases([record(), record("b", "a", "test")])


def test_invalid_label_version_and_duplicate():
    r = record()
    r["expected_assignments"]["allergies"] = [999]
    with pytest.raises(ValueError):
        validate_cases([r])
    r = record()
    r["segmentation_version"] = "other"
    with pytest.raises(ValueError):
        validate_cases([r])
    with pytest.raises(ValueError):
        validate_cases([record(), record()])


def test_unreviewed_fixtures_do_not_export(tmp_path):
    cases = validate_cases(
        json.loads(Path("evaluation/fixtures/development.json").read_text())
    )
    with pytest.raises(ValueError, match="No reviewed"):
        export_cases(cases, tmp_path / "export")
    assert not (tmp_path / "export").exists()
