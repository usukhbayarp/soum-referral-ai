"""Export and measure reviewed data; this command NEVER starts training."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from app.core import (
    ROOT,
    PROMPT_VERSION,
    SCHEMA,
    SEGMENTATION_VERSION,
    OUTPUT_SCHEMA_VERSION,
)
from scripts.dataset import validate_cases, export_cases


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def serving_contract():
    return {
        "prompt": PROMPT_VERSION,
        "schema": SCHEMA["version"],
        "segmentation": SEGMENTATION_VERSION,
        "output": OUTPUT_SCHEMA_VERSION,
    }


def verify_model_files(model, provenance):
    for name, entry in provenance["files"].items():
        if sha256(model / name) != entry["sha256"]:
            raise ValueError(
                "Prepared model/tokenizer files changed; reverify provenance"
            )


def require_splits(cases):
    for split in ("train", "development"):
        if not any(
            c.split == split and c.clinician_review_status == "reviewed" for c in cases
        ):
            raise ValueError(f"Separate reviewed {split} examples are required")
    if not any(c.split == "test" for c in cases):
        raise ValueError("Supply all splits, including a preserved held-out test set")


def check_versions(pins):
    versions = {
        name: importlib.metadata.version(name)
        for name in ("mlx", "mlx-lm", "transformers")
    }
    if any(versions[name] != pins[name] for name in versions):
        raise ValueError(
            "MLX/tokenizer versions changed; reverify masking/export before training"
        )
    return versions


def prepare_experiment(source, output, model):
    cases = validate_cases(json.loads(source.read_text()))
    require_splits(cases)
    pins = json.loads((ROOT / "training/pins.json").read_text())
    baseline = json.loads(
        (ROOT / "evaluation/results/comparison-20261004T052629Z.json").read_text()
    )
    template = next(
        m["template"] for m in baseline["models"] if m["identifier"] == "qwen3:1.7b"
    )
    if hashlib.sha256(template.encode()).hexdigest() != pins["serving_template_sha256"]:
        raise ValueError("Serving template changed; reverify training tokenization")
    versions = check_versions(pins)
    model = model.resolve()
    provenance_path = model / "preparation-provenance.json"
    provenance = json.loads(provenance_path.read_text())
    if (
        provenance["base_revision"] != pins["base_revision"]
        or provenance["quantization"] != pins["mlx_quantization"]
    ):
        raise ValueError("MLX checkpoint provenance does not match pins")
    verify_model_files(model, provenance)
    from transformers import AutoTokenizer
    from scripts.training_tokens import checked_tokens, TEMPLATE_POLICY

    tokenizer = AutoTokenizer.from_pretrained(
        model, local_files_only=True, trust_remote_code=False
    )
    if output.exists():
        raise ValueError("Choose a new experiment directory")
    export_cases(cases, output / "data")
    lengths = []
    for split, filename in (("train", "train.jsonl"), ("development", "valid.jsonl")):
        records = [
            json.loads(line)
            for line in (output / "data" / filename).read_text().splitlines()
        ]
        for index, record in enumerate(records):
            tokens, offset = checked_tokens(record, tokenizer)
            lengths.append(
                {
                    "split": split,
                    "index": index,
                    "prompt_tokens": offset,
                    "completion_tokens": len(tokens) - offset,
                    "full_tokens": len(tokens),
                }
            )
    maximum = max(row["full_tokens"] for row in lengths)
    config = json.loads((ROOT / "training/smoke.json").read_text())
    config["max_seq_length"] = ((maximum + 31) // 32) * 32
    config["model"] = str(model)
    config["data"] = str((output / "data").resolve())
    if config["max_seq_length"] > 16384:
        raise ValueError(
            "Measured sequence exceeds serving context; revise the contract/data explicitly"
        )
    (output / "smoke.json").write_text(json.dumps(config, indent=2) + "\n")
    manifest = {
        "status": "prepared_only_not_trained",
        "template_policy": TEMPLATE_POLICY,
        "serving_contract": serving_contract(),
        "runner_sha256": {
            name: sha256(ROOT / "scripts" / name)
            for name in (
                "training_prepare.py",
                "training_tokens.py",
                "training_smoke.py",
                "dataset.py",
            )
        },
        "pins": pins,
        "versions": versions,
        "canonical_dataset_sha256": sha256(source),
        "model_provenance_sha256": sha256(provenance_path),
        "files_sha256": {
            str(p.relative_to(output)): sha256(p)
            for p in output.rglob("*")
            if p.is_file()
        },
        "contract_sha256": {
            p.name: sha256(p) for p in sorted((ROOT / "config").glob("*"))
        },
        "full_sequence_measurements": lengths,
        "held_out_test_count": sum(c.split == "test" for c in cases),
        "loss": "completion-only, excludes prompt and padding, includes assistant EOS",
        "checkpoint_selection": "lowest full reviewed-development completion loss; not clinical accuracy",
    }
    (output / "preflight.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Prepared {len(lengths)} reviewed records; full tokens max={maximum}; sequence limit={config['max_seq_length']}. No training started."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, help="Full canonical dataset with all splits"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model", type=Path, default=ROOT / ".runtime/preparation/qwen3-1.7b-mlx4"
    )
    args = parser.parse_args()
    try:
        prepare_experiment(args.input, args.output, args.model)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Preflight blocked: {error}\n")


if __name__ == "__main__":
    main()
