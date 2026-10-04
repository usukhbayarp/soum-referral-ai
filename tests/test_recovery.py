import copy
import json
import pytest
from scripts.recovery import (
    CONTRACT,
    DESIGN,
    assignment_score,
    fixtures,
    merge_outputs,
    presentation,
    requests,
)
from app.core import ExtractionError, prepare, resolve
from app.adapter import OPTIONS


def test_presentation_keeps_original_note_offsets_and_one_id_namespace():
    note = fixtures()[0]["source_note"]
    units, calls = requests(note, "qwen3:1.7b", True)
    original = copy.deepcopy(units)
    shown = presentation(units)
    assert units == original
    assert all(note[u["start"] : u["end"]] == u["text"] for u in units)
    assert all(set(u) == {"id", "text"} for u in shown)
    assert all(not u["text"].startswith("[S") for u in shown)
    assert [u["id"] for u in shown] == list(range(1, 34))
    assert units[0]["text"].startswith("[S01]")
    # Every call receives every unit; no example/reference assignment is supplied.
    for call in calls:
        payload = json.loads(call["messages"][1]["content"])
        assert payload["source_units"] == shown
        assert set(payload) == {"headings", "source_units"}
        assert set(payload["headings"]) == set(call["format"]["required"])
        assert call["options"] == OPTIONS
        assert call["keep_alive"] == 0 and call["think"] is False


def test_group_coverage_strict_atomic_resolution_and_abstentions():
    case = fixtures()[0]
    units, calls = requests(case["source_note"], "qwen3:1.7b", True)
    groups = DESIGN["groups"]
    flat = [k for group in groups for k in group]
    assert len(flat) == len(set(flat)) == len(CONTRACT.fields)
    assert set(flat) == set(CONTRACT.assignment.model_fields)
    raws = [json.dumps({k: case["expected_assignments"][k] for k in g}) for g in groups]
    actual = merge_outputs(raws, groups, units)
    assert actual == case["expected_assignments"]
    assert (
        resolve(json.dumps(actual), units, CONTRACT)["identity_source"]["evidence"][0]
        == units[0]
    )
    empty = [json.dumps({k: [] for k in g}) for g in groups]
    assert all(v == [] for v in merge_outputs(empty, groups, units).values())
    for bad in [
        "{}",
        '{"identity_source":[],"identity_source":[]}',
        raws[0].replace("[1, 2, 3, 4, 5]", "[999]"),
        raws[0].replace("[1, 2, 3, 4, 5]", "[true]"),
    ]:
        with pytest.raises((ValueError, ExtractionError)):
            merge_outputs([bad] + raws[1:], groups, units)
    with pytest.raises(ValueError):
        merge_outputs(raws[:-1], groups, units)


def test_baseline_request_matches_current_contract_and_keeps_scoring_separate():
    units, calls = requests(fixtures()[0]["source_note"], "qwen3:4b", False)
    original, user, schema = prepare(fixtures()[0]["source_note"], CONTRACT)
    assert len(calls) == 1 and units == original
    assert calls[0]["messages"] == [
        {"role": "system", "content": CONTRACT.system},
        {"role": "user", "content": user},
    ]
    assert calls[0]["format"] == schema
    assert assignment_score({"x": [1, 2]}, {"x": [2, 3]})["x"] == {
        "expected": [1, 2],
        "actual": [2, 3],
        "exact": False,
        "missing": [1],
        "extra": [3],
    }
    assert assignment_score(None, {"x": []}) is None
    assert all(
        c["split"] == "development" and c["clinician_review_status"] == "unreviewed"
        for c in fixtures()
    )
