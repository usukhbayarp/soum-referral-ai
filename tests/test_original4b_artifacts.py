"""Post-run mechanics checks over new results; never open held-out content."""

import json
from pathlib import Path
import pytest
from scripts import medication_experiment as frozen
from scripts.original4b_comparison import OUT, TAG


def test_official_artifact_manifest_and_identity():
    meta = json.loads((OUT / "Qwen3-4B-GGUF-manifest.json").read_text())
    assert meta["cardData"]["base_model"] == "Qwen/Qwen3-4B"
    entry = next(
        f for f in meta["siblings"] if f["rfilename"] == "Qwen3-4B-Q4_K_M.gguf"
    )
    download = json.loads((OUT / "download.json").read_text())
    assert download["verified"] and download["sha256"] == entry["lfs"]["sha256"]
    assert download["bytes"] == entry["size"]
    gguf = json.loads((OUT / "gguf-metadata.json").read_text())
    assert gguf["general.architecture"] == "qwen3" and gguf["qwen3.block_count"] == 36
    assert gguf["general.file_type"] == 15
    smoke = json.loads((OUT / "smoke.json").read_text())
    assert smoke["pass"] and not smoke["response"]["message"].get("thinking")


@pytest.mark.parametrize("revision", [1, 2])
def test_frozen_requests_and_all_cases_preserved(revision):
    path = OUT / f"run-v{revision}/report.json"
    if not path.exists() or "finished_utc" not in json.loads(path.read_text()):
        pytest.skip("bounded experiment not yet complete")
    report = json.loads(path.read_text())
    baseline = json.loads((frozen.DATA / f"run-v{revision}/report.json").read_text())
    assert len(report["runs"]) == len(baseline["runs"]) == (10 if revision == 1 else 8)
    for actual, prior in zip(report["runs"], baseline["runs"]):
        assert actual["request"]["model"] == TAG
        assert {k: v for k, v in actual["request"].items() if k != "model"} == {
            k: v for k, v in prior["request"].items() if k != "model"
        }
        assert actual["original_source"] == prior["original_source"]
        assert actual["source_mapping"] == prior["source_mapping"]
        assert (actual["candidate"], actual["case_id"], actual["repeat"]) == (
            prior["candidate"],
            prior["case_id"],
            prior["repeat"],
        )
        assert json.loads(actual["serialized_request"]) == actual["request"]
        assert actual["wall_seconds"] < 61
        if actual.get("validation"):
            replay = frozen.validate_output(
                actual["candidate"],
                frozen.validate_envelope(actual["response"]),
                actual["source_mapping"],
            )
            assert replay == actual["validation"]
