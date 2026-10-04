import copy
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.core import CONTRACT, Contract, prepare, resolve, segment
from app.main import create_app
from scripts.dataset import validate_cases, export_cases

ROOT = Path(__file__).resolve().parents[1]


def cases():
    return json.loads((ROOT / "evaluation/dev002-v06/cases.json").read_text())


def test_source_exact_hash_mapping_and_no_reference_in_example():
    case = cases()[0]
    provenance = json.loads(
        (ROOT / "evaluation/dev002-v06/provenance.json").read_text()
    )
    assert (
        hashlib.sha256(case["source_note"].encode()).hexdigest()
        == provenance["source_note_sha256"]
    )
    assert (
        case["source_note"] + "\n"
        == (ROOT / "evaluation/dev002-v06/source-note.txt").read_text()
    )
    mapping = json.loads((ROOT / "evaluation/dev002-v06/source-map.json").read_text())
    assert mapping["units"] == segment(case["source_note"])
    assert sorted(
        i for ids in mapping["original_to_internal"].values() for i in ids
    ) == list(range(1, 34))
    response = TestClient(create_app()).get("/api/example/dev002").json()
    assert response["source_note"] == case["source_note"]
    assert "expected_assignments" not in response and "reference" not in response
    assert response["clinician_review_status"] == "unreviewed"


def test_v06_preserves_regular_administered_initial_current_and_negative_states():
    case = cases()[0]
    units, user, schema = prepare(case["source_note"])
    fields = resolve(json.dumps(case["expected_assignments"]), units)
    assert "Амлодипин" in fields["regular_medication"]["text"]
    assert "асуугаагүй" in fields["regular_medication"]["text"]
    assert "парацетамол" in fields["treatment_source"]["text"]
    assert "Амлодипин" not in fields["treatment_source"]["text"]
    assert (
        "10:05" in fields["initial_source"]["text"]
        and "11:00" not in fields["initial_source"]["text"]
    )
    assert (
        "11:00" in fields["current_source"]["text"]
        and "10:05" not in fields["current_source"]["text"]
    )
    assert "үнэлээгүй" in fields["examination"]["text"]
    assert "харшилгүй гэж хэлэв" in fields["allergies"]["text"]
    assert "байхгүй" in fields["pending_results"]["text"]
    assert [e["id"] for e in fields["pain_change"]["evidence"]] == [18, 22]
    assert "2026.10.04" not in fields["treatment_source"]["text"]  # no date synthesis
    assert len((CONTRACT.system + user).encode()) <= 12000
    assert len(case["source_note"]) == 1620


def test_dev_family_and_reviewed_export_protection(tmp_path):
    records = cases()
    with pytest.raises(ValueError, match="No reviewed"):
        export_cases(validate_cases(records), tmp_path / "no-export")
    for split in ["test", "train"]:
        changed = copy.deepcopy(records)
        changed[0]["split"] = split
        with pytest.raises(ValueError, match="development-only"):
            validate_cases(changed)
    changed = copy.deepcopy(records)
    changed[0]["underlying_case_id"] = "another"
    with pytest.raises(ValueError, match="variants"):
        validate_cases(changed)
    variant = copy.deepcopy(records[0])
    variant["case_id"] = "DEV-002-reordered"
    variant["source_note"] = "\n".join(reversed(variant["source_note"].splitlines()))
    variant["expected_assignments"] = None
    assert len(validate_cases(records + [variant])) == 2


def test_legacy_contracts_remain_valid_and_cannot_be_relabelled():
    old = json.loads((ROOT / "evaluation/fixtures/development.json").read_text())
    assert len(validate_cases(old)) == 5
    assert (
        Contract("provisional-0.1", "source-id-1").schema["version"]
        == "provisional-0.1"
    )
    with pytest.raises(ValueError):
        Contract("experimental-0.6", "source-id-2")
    changed = cases()
    changed[0]["prompt_version"] = "source-id-2"
    with pytest.raises(ValueError):
        validate_cases(changed)
    changed = cases()
    changed[0].pop("prompt_version")
    with pytest.raises(ValueError):
        validate_cases(changed)


def test_new_export_uses_same_active_contract(tmp_path):
    # Unit-test-only fake label approval; never persisted to the actual DEV-002 data.
    case = cases()[0]
    case["case_id"] = "unit-synthetic"
    case["underlying_case_id"] = "unit-synthetic"
    case["source_note"] = case["source_note"].replace("DEV-002", "UNIT-00")
    case["clinician_review_status"] = "reviewed"
    output = tmp_path / "export"
    export_cases(validate_cases([case]), output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["schema_version"] == "experimental-0.6"
    assert manifest["prompt_version"] == "source-id-v06-1"
    messages = json.loads((output / "valid.jsonl").read_text())["messages"]
    assert messages[0]["content"] == CONTRACT.system
    assert messages[1]["content"] == prepare(case["source_note"])[1]
    assert set(json.loads(messages[2]["content"])) == set(
        CONTRACT.assignment.model_fields
    )


def test_structural_cross_group_reuse_is_flagged_not_silently_verified():
    case = cases()[0]
    assignments = copy.deepcopy(case["expected_assignments"])
    assignments["initial_source"] = [14, 25]
    assignments["treatment_source"] = [11, 21]
    fields = resolve(json.dumps(assignments), segment(case["source_note"]))
    assert fields["initial_source"]["review_flags"]
    assert fields["current_source"]["review_flags"]
    assert fields["regular_medication"]["review_flags"]
    assert fields["treatment_source"]["review_flags"]
    # Only original text; flags do not perform clinical correction or invent values.
    assert fields["treatment_source"]["text"] == "\n".join(
        segment(case["source_note"])[i - 1]["text"] for i in [11, 21]
    )
