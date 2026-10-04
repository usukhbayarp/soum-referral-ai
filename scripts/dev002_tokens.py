"""Measure the new fictional development contract; no model load or training."""

import json
from pathlib import Path
from app.core import ROOT, SYSTEM, SCHEMA, PROMPT_VERSION, prepare
from scripts.training_tokens import checked_tokens
from scripts.training_prepare import sha256


def main():
    from transformers import AutoTokenizer

    case = json.loads((ROOT / "evaluation/dev002-v06/cases.json").read_text())[0]
    if (
        case["schema_version"] != SCHEMA["version"]
        or case["prompt_version"] != PROMPT_VERSION
    ):
        raise ValueError("Active contract mismatch")
    model = ROOT / ".runtime/preparation/qwen3-1.7b-mlx4"
    tokenizer = AutoTokenizer.from_pretrained(
        model, local_files_only=True, trust_remote_code=False
    )
    _, user, _ = prepare(case["source_note"])
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
        {
            "role": "assistant",
            "content": json.dumps(
                case["expected_assignments"], ensure_ascii=False, separators=(",", ":")
            ),
        },
    ]
    tokens, offset = checked_tokens({"messages": messages}, tokenizer, max_length=16384)
    output = ROOT / f"evaluation/dev002-v06/token-audit-{PROMPT_VERSION}.json"
    if output.exists():
        raise ValueError("Refusing overwrite")
    report = dict(
        schema_version=SCHEMA["version"],
        prompt_version=PROMPT_VERSION,
        case_id="DEV-002",
        status="unreviewed development mechanics; no training",
        source_chars=len(case["source_note"]),
        source_sha256=sha256(ROOT / "evaluation/dev002-v06/source-note.txt"),
        prompt_tokens=offset,
        target_tokens=len(tokens) - offset,
        full_tokens=len(tokens),
        serving_context=16384,
        serving_output_bound=1600,
        non_thinking_and_completion_mask_verified=True,
        tokenizer_files={
            n: sha256(model / n) for n in ["tokenizer.json", "tokenizer_config.json"]
        },
    )
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
