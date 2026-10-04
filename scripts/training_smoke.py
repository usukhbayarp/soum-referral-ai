"""Explicit later opt-in: five MLX LoRA steps, never run by preparation/export."""

import argparse
import json
import math
import os
from pathlib import Path
from app.core import ROOT
from scripts.training_prepare import (
    sha256,
    check_versions,
    serving_contract,
    verify_model_files,
)


def verify_preflight(directory):
    manifest = json.loads((directory / "preflight.json").read_text())
    current_pins = json.loads((ROOT / "training/pins.json").read_text())
    if manifest["pins"] != current_pins:
        raise ValueError("Pins changed; prepare a fresh experiment")
    check_versions(current_pins)
    if manifest["serving_contract"] != serving_contract():
        raise ValueError("Selected prompt/schema versions changed; repeat preflight")
    from scripts.training_tokens import TEMPLATE_POLICY

    if manifest["template_policy"] != TEMPLATE_POLICY:
        raise ValueError("Template policy changed; repeat preflight")
    for name, digest in manifest["runner_sha256"].items():
        if sha256(ROOT / "scripts" / name) != digest:
            raise ValueError("Training/export code changed; repeat preflight")
    for name, digest in manifest["files_sha256"].items():
        if sha256(directory / name) != digest:
            raise ValueError("Prepared dataset/config changed; repeat preflight")
    for name, digest in manifest["contract_sha256"].items():
        if sha256(ROOT / "config" / name) != digest:
            raise ValueError("Serving contract changed; repeat review and preflight")
    config = json.loads((directory / "smoke.json").read_text())
    if not 1 <= config["iters"] <= 10 or config["batch_size"] != 1:
        raise ValueError("This runner is bounded to 1–10 steps and batch size 1")
    if (
        sha256(Path(config["model"]) / "preparation-provenance.json")
        != manifest["model_provenance_sha256"]
    ):
        raise ValueError("Model provenance changed")
    model = Path(config["model"])
    verify_model_files(
        model, json.loads((model / "preparation-provenance.json").read_text())
    )
    return config


def run(directory):
    config = verify_preflight(directory)
    os.environ["HF_HUB_OFFLINE"] = "1"
    from transformers import AutoTokenizer
    import mlx.core as mx
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten
    from mlx_lm.utils import load
    from mlx_lm.tuner.utils import linear_to_lora_layers
    from mlx_lm.tuner.trainer import train, evaluate, TrainingArgs
    from scripts.training_tokens import checked_tokens, completion_loss

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"], local_files_only=True, trust_remote_code=False
    )
    datasets = []
    for filename in ("train.jsonl", "valid.jsonl"):
        records = [
            json.loads(line)
            for line in (directory / "data" / filename).read_text().splitlines()
        ]
        if not records:
            raise ValueError("Both reviewed splits must be nonempty")
        datasets.append(
            [checked_tokens(r, tokenizer, config["max_seq_length"]) for r in records]
        )
    if (directory / "data/test.jsonl").exists():
        raise ValueError("Held-out tests must not be in the training export")
    adapters = directory / "adapters"
    best = directory / "best"
    if adapters.exists() or best.exists():
        raise ValueError(
            "Experiment already started; use a fresh preparation directory"
        )
    adapters.mkdir()
    best.mkdir()
    mx.random.seed(config["seed"])
    model, _ = load(config["model"], tokenizer_config={"trust_remote_code": False})
    model.freeze()
    linear_to_lora_layers(model, config["num_layers"], config["lora_parameters"])
    adapter_config = {**config, "fine_tune_type": "lora"}
    for path in (adapters, best):
        (path / "adapter_config.json").write_text(json.dumps(adapter_config, indent=2))

    class Selection:
        best_loss = float("inf")

        def on_train_loss_report(self, info):
            self.record("train", info)

        def record(self, kind, info):
            with (directory / "metrics.jsonl").open("a") as stream:
                stream.write(json.dumps({"kind": kind, **info}) + "\n")

        def on_val_loss_report(self, info):
            self.record("development", info)
            loss = info["val_loss"]
            if not math.isfinite(loss):
                raise ValueError("Non-finite development loss")
            if loss < self.best_loss:
                self.best_loss = loss
                mx.save_safetensors(
                    str(best / "adapters.safetensors"),
                    dict(tree_flatten(model.trainable_parameters())),
                )
                (best / "selection.json").write_text(
                    json.dumps(
                        {
                            **info,
                            "criterion": "reviewed-development completion loss",
                            "clinical_quality": "unmeasured",
                        },
                        indent=2,
                    )
                )

    selection = Selection()
    args = TrainingArgs(
        **{
            k: config[k]
            for k in (
                "batch_size",
                "iters",
                "val_batches",
                "steps_per_report",
                "steps_per_eval",
                "steps_per_save",
                "max_seq_length",
                "grad_checkpoint",
            )
        },
        adapter_file=adapters / "adapters.safetensors"
    )
    train(
        model,
        optim.Adam(learning_rate=config["learning_rate"]),
        datasets[0],
        datasets[1],
        args=args,
        loss=completion_loss,
        training_callback=selection,
    )
    # MLX 0.30.7 validates BEFORE the step. Explicitly evaluate final weights too.
    model.eval()
    loss = evaluate(
        model,
        datasets[1],
        batch_size=1,
        num_batches=-1,
        max_seq_length=config["max_seq_length"],
        loss=completion_loss,
    )
    selection.on_val_loss_report({"iteration": config["iters"], "val_loss": loss})
    (directory / "completed.json").write_text(
        json.dumps(
            {
                "steps": config["iters"],
                "peak_memory_bytes": mx.get_peak_memory(),
                "selected": "best",
                "training_quality_claim": None,
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--schema-approved",
        action="store_true",
        help="Explicit human attestation that the reviewed schema is ready for this experiment",
    )
    args = parser.parse_args()
    if not args.schema_approved:
        parser.error(
            "Final schema approval and reviewed data are required; training not started"
        )
    run(args.directory.resolve())


if __name__ == "__main__":
    main()
