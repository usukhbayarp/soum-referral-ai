"""Tokenizer/masking mechanics on fictional fixtures; no training or reviewed labels."""

import argparse
import json
from pathlib import Path
from app.core import ROOT, SYSTEM, Assignment, prepare, SCHEMA, PROMPT_VERSION
from scripts.training_prepare import sha256
from scripts.training_tokens import checked_tokens, completion_loss, TEMPLATE_POLICY


def audit(tokenizer_path, output):
    from transformers import AutoTokenizer
    import mlx.core as mx

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path, local_files_only=True, trust_remote_code=False
    )
    fixture_path = ROOT / "evaluation/fixtures/development.json"
    baseline_path = ROOT / "evaluation/results/comparison-20261004T052629Z.json"
    fixtures = json.loads(fixture_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    if (
        baseline["schema_version"] != SCHEMA["version"]
        or baseline["prompt_version"] != PROMPT_VERSION
    ):
        raise ValueError(
            "Historical audit requires REFERRAL_SCHEMA_VERSION=provisional-0.1 and EXTRACTION_PROMPT_VERSION=source-id-2; use dev002_tokens for v0.6"
        )
    model = next(m for m in baseline["models"] if m["identifier"] == "qwen3:1.7b")
    rows = []
    for case, result in zip(fixtures, model["cases"], strict=True):
        assert case["case_id"] == result["case_id"]
        _, user, _ = prepare(case["source_note"])
        target = Assignment.model_validate_json(
            result["output"]["raw_output"]
        ).model_dump_json()
        record = {
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
                {"role": "assistant", "content": target},
            ]
        }
        tokens, offset = checked_tokens(record, tokenizer)
        rows.append(
            {
                "case_id": case["case_id"],
                "prompt_tokens": offset,
                "completion_tokens": len(tokens) - offset,
                "full_tokens": len(tokens),
            }
        )
    # Numerical loss check only. No optimizer, real model, or parameter update.
    batch = mx.array([[9, 8, 2, 3, 0, 0]])
    lengths = mx.array([[2, 4]])
    loss, count = completion_loss(lambda inputs: mx.zeros((1, 5, 10)), batch, lengths)
    mx.eval(loss, count)
    assert count.item() == 2 and abs(loss.item() - 2.302585) < 0.0001
    report = {
        "purpose": "mechanics only; targets are preserved unreviewed baseline outputs, NOT clinician labels",
        "fixture_sha256": sha256(fixture_path),
        "baseline_sha256": sha256(baseline_path),
        "tokenizer_sha256": {
            name: sha256(tokenizer_path / name)
            for name in (
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.json",
                "merges.txt",
            )
        },
        "measurements": rows,
        "non_thinking_prefix_verified": True,
        "completion_mask_probe": {
            "prompt_and_padding_excluded": True,
            "completion_token_count": count.item(),
        },
        "training_started": False,
        "template_policy": TEMPLATE_POLICY,
    }
    if output.exists():
        raise ValueError("Refusing to overwrite an audit")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.tokenizer, args.output)
