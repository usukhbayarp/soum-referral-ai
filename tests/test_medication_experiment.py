import copy, json, subprocess
import pytest
from scripts.medication_experiment import *


def test_exact_original_offsets_paragraphs_single_namespace_no_answer_leakage():
    c = load_cases()[0]
    view, mapping = model_view(c["source_note"])
    assert len(view["paragraphs"]) == 11 and len(mapping) == 33
    assert mapping["U1"]["text"].startswith("[S01]")
    for u in mapping.values():
        assert c["source_note"][u["start"] : u["end"]] == u["text"]
    a, _ = request("A", c["source_note"])
    b, _ = request("B", c["source_note"])
    assert a["messages"][1] == b["messages"][1]
    payload = json.loads(a["messages"][1]["content"])
    assert set(payload) == {"role_definitions", "paragraphs"}
    assert all(
        set(u) == {"id", "text"} and not u["text"].startswith("[S")
        for p in payload["paragraphs"]
        for u in p
    )
    assert "expected" not in payload and "DEV-002" in a["messages"][1]["content"]
    assert a["options"] == b["options"] == SETTINGS
    for x in [a, b]:
        assert x["think"] is False and x["stream"] is False and x["keep_alive"] == "5m"


def test_unit_roles_require_every_key_and_mixed_stays_visible():
    c = load_cases()[-1]
    _, mapping = model_view(c["source_note"])
    data = {k: "other" for k in mapping}
    data["U1"] = "mixed_or_unclear"
    result = validate_output("A", json.dumps(data), mapping)
    assert result["groups"]["mixed_or_unclear"][0]["text"] == mapping["U1"]["text"]
    assert result["review_flags"]
    for change in [
        {},
        {**data, "bogus": "other"},
        {**data, "U1": ["regular_medication", "administered_treatment"]},
        {**data, "U1": "wrong"},
    ]:
        with pytest.raises(ValueError):
            validate_output("A", json.dumps(change), mapping)
    with pytest.raises(ValueError):
        validate_output("A", '{"U1":"other","U1":"other"}', mapping)


def test_incomplete_never_accepted_even_if_parseable():
    for data in [
        {"done": False, "message": {"content": "{}"}},
        {"done": True, "done_reason": "length", "message": {"content": "{}"}},
        {
            "done": True,
            "done_reason": "stop",
            "message": {"thinking": "text", "content": "{}"},
        },
    ]:
        with pytest.raises(ValueError):
            validate_envelope(data)
    assert (
        validate_envelope(
            {"done": True, "done_reason": "stop", "message": {"content": "{}"}}
        )
        == "{}"
    )


def test_repeated_quote_uses_unit_then_flags_within_unit_ambiguity():
    _, mapping = model_view("эм эм.\nэм эм.")
    spans, errors, flags = quote_locations(
        [{"source_unit": "U2", "quote": "эм эм."}], mapping
    )
    assert (
        not errors and not flags and spans[0]["locations"] == [{"start": 7, "end": 13}]
    )
    spans, errors, flags = quote_locations(
        [{"source_unit": "U2", "quote": "эм"}], mapping
    )
    assert (
        len(spans[0]["locations"]) == 2
        and flags[0]["type"] == "ambiguous_repeated_quote"
    )


def med_output(mapping, dose="5 мг"):
    return {
        "medications": [
            {
                "role": "regular_medication",
                "name": "амлодипин",
                "dose": dose,
                "route": None,
                "time": None,
                "frequency": None,
                "evidence": [{"source_unit": "U1", "quote": mapping["U1"]["text"]}],
            }
        ],
        "allergies": [],
        "medication_context": [],
    }


def test_lexical_match_does_not_certify_wrong_drug_dose_association():
    _, mapping = model_view(load_cases()[-1]["source_note"])
    data = med_output(
        mapping, "500 мг"
    )  # actually belongs to paracetamol in the SAME unit
    result = validate_output("B", json.dumps(data), mapping)
    assert result["evidence_valid"]
    assert any(
        f["type"] == "drug_detail_role_association_requires_review"
        for f in result["review_flags"]
    )
    assert (
        result["output"]["medications"][0]["dose"] == "500 мг"
    )  # retained for audit, never repaired
    bad = med_output(mapping, "999 мг")
    r = validate_output("B", json.dumps(bad), mapping)
    assert not r["evidence_valid"] and r["output"] == bad
    bad["medications"][0]["evidence"][0]["source_unit"] = "U999"
    with pytest.raises(ValueError):
        validate_output("B", json.dumps(bad), mapping)


def test_allergy_must_be_intact_and_empty_lists_remain_explicit():
    _, mapping = model_view("Эмийн харшилгүй гэж өвчтөн хэлсэн.")
    result = {
        "medications": [],
        "allergies": [
            {
                "statement": "Эмийн харшилгүй",
                "evidence": [{"source_unit": "U1", "quote": mapping["U1"]["text"]}],
            }
        ],
        "medication_context": [],
    }
    assert not validate_output("B", json.dumps(result), mapping)["evidence_valid"]
    result["allergies"][0]["statement"] = mapping["U1"]["text"]
    assert validate_output("B", json.dumps(result), mapping)["evidence_valid"]
    result["allergies"] = []
    assert validate_output("B", json.dumps(result), mapping)["output"] == result
    result["extra"] = []
    with pytest.raises(ValueError):
        validate_output("B", json.dumps(result), mapping)


def test_fixed_development_cases_and_production_defaults_unchanged():
    cases = load_cases()
    assert len(cases) == 4 and all(
        c["split"] == "development" and c["clinician_review_status"] == "unreviewed"
        for c in cases
    )
    old = json.loads((ROOT / "evaluation/fixtures/development.json").read_text())
    for c in cases[1:3]:
        assert (
            c["source_note"]
            == next(x for x in old if x["case_id"] == c["case_id"])["source_note"]
        )
    assert (
        cases[0]["source_note"]
        == json.loads((ROOT / "evaluation/dev002-v06/cases.json").read_text())[0][
            "source_note"
        ]
    )
    for path in [
        "app/adapter.py",
        "app/core.py",
        "config/referral.v0.6.json",
        "config/extraction.source-id-v06-1.txt",
    ]:
        baseline = subprocess.check_output(
            ["git", "show", f"624411c9e10477ee4898412abcf03d08a8e0fd39:{path}"],
            cwd=ROOT,
        )
        assert (ROOT / path).read_bytes() == baseline
