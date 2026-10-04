import copy
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from app.adapter import OllamaAdapter
from app.main import create_app
from scripts.import_candidate import require_new_tag
from scripts.training_prepare import require_splits
from scripts.compare_reports import compare
from scripts.training_tokens import NonThinkingTokenizer
from scripts.training_prepare import sha256, verify_model_files


def case(split, reviewed=True):
    return SimpleNamespace(
        split=split, clinician_review_status="reviewed" if reviewed else "unreviewed"
    )


@pytest.mark.parametrize(
    "cases",
    [
        [case("train"), case("test")],
        [case("development"), case("test")],
        [case("train"), case("development")],
        [case("train", False), case("development"), case("test")],
    ],
)
def test_training_requires_both_reviewed_splits_and_held_out(cases):
    with pytest.raises(ValueError):
        require_splits(cases)


def test_held_out_labels_need_not_be_loaded_into_training():
    require_splits([case("train"), case("development"), case("test", False)])


@pytest.mark.parametrize(
    "tag", ["qwen3:1.7b", "qwen3:4b", "soum-existing:v1", "soum-unversioned"]
)
def test_import_cannot_overwrite_or_use_baseline_tags(tag):
    with pytest.raises(ValueError):
        require_new_tag(tag, {"soum-existing:v1": "digest"})


def test_new_versioned_candidate_allowed():
    require_new_tag("soum-candidate:experiment-1", {"qwen3:1.7b": "preserved"})


def test_template_policy_mirrors_serving_without_mutating_canonical_messages():
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["enable_thinking"] is False
            return messages

    messages = [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "SOURCE"},
    ]
    original = copy.deepcopy(messages)
    result = NonThinkingTokenizer(Tokenizer()).apply_chat_template(
        messages, enable_thinking=True
    )
    assert result[0]["content"] == "\nSYSTEM"
    assert result[1]["content"] == "SOURCE /no_think"
    assert messages == original
    with pytest.raises(ValueError, match="single-turn"):
        NonThinkingTokenizer(Tokenizer()).apply_chat_template(messages + messages)


def test_modified_model_or_tokenizer_blocks_preflight(tmp_path):
    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"unit-test placeholder, not model weights")
    provenance = {"files": {weights.name: {"sha256": sha256(weights)}}}
    verify_model_files(tmp_path, provenance)
    weights.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        verify_model_files(tmp_path, provenance)


def test_comparison_preserves_invalid_and_abstaining_cases():
    path = (
        Path(__file__).parents[1]
        / "evaluation/results/comparison-20261004T052629Z.json"
    )
    baseline = json.loads(path.read_text())
    candidate = copy.deepcopy(baseline)
    model = candidate["models"][0]
    model["identifier"] = "soum-candidate:v1"
    failure = model["cases"][0]
    failure["validation_error"] = "incomplete_output"
    failure["abstentions"] = None
    failure.pop("output")
    result = compare(
        baseline, candidate, baseline["models"][0]["identifier"], model["identifier"]
    )
    assert len(result["cases"]) == 5
    assert result["candidate_invalid"] == 1
    assert result["cases"][0]["assignment_agreement"] is None
    assert result["cases"][0]["candidate_abstentions"] is None
    assert (
        result["cases"][1]["candidate_abstentions"] == model["cases"][1]["abstentions"]
    )
    candidate["settings"]["num_ctx"] = 512
    with pytest.raises(ValueError, match="settings"):
        compare(
            baseline,
            candidate,
            baseline["models"][0]["identifier"],
            model["identifier"],
        )


@pytest.mark.parametrize("local,expected", [(False, 503), (True, 200)])
def test_liveness_and_model_readiness_are_separate_and_do_not_infer(local, expected):
    requests = []

    def handle(request):
        requests.append(request.url.path)
        assert request.method == "GET" and request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": (
                    [
                        {
                            "name": "qwen3:1.7b",
                            "digest": "test",
                            "details": {"format": "gguf"},
                        }
                    ]
                    if local
                    else []
                )
            },
        )

    adapter = OllamaAdapter(transport=httpx.MockTransport(handle))
    client = TestClient(create_app(adapter))
    assert client.get("/api/health").status_code == 200
    assert requests == []
    response = client.get("/api/ready")
    assert response.status_code == expected
    assert requests == ["/api/tags"]
    if local:
        assert response.json()["inference_verified"] is False


def test_unreachable_runtime_does_not_break_liveness_or_expose_details():
    def handle(request):
        raise httpx.ConnectError("internal detail must not escape")

    client = TestClient(
        create_app(OllamaAdapter(transport=httpx.MockTransport(handle)))
    )
    assert client.get("/api/health").status_code == 200
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json()["error"] == "runtime_unavailable"
    assert "internal detail" not in response.text
