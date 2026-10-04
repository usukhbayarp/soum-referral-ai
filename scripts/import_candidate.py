"""Import a NEW local candidate; preserve the baseline tag and chat template."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import httpx
from app.adapter import OllamaAdapter
from app.core import ROOT


def require_new_tag(tag, existing):
    OllamaAdapter(model=tag)  # Same local-identifier validation as serving.
    if not tag.startswith("soum-") or ":" not in tag or tag in existing:
        raise ValueError(
            "Use a new, explicitly versioned soum- tag; existing tags cannot be overwritten"
        )


def import_candidate(gguf, tag, output):
    if output.exists():
        raise ValueError("Choose a new import provenance directory")
    gguf = gguf.resolve(strict=True)
    with gguf.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("Input is not GGUF")
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    base = ROOT / "evaluation/results/comparison-20261004T052629Z.json"
    report = json.loads(base.read_text())
    baseline = next(m for m in report["models"] if m["identifier"] == "qwen3:1.7b")
    template = baseline["template"]
    pins = json.loads((ROOT / "training/pins.json").read_text())
    if hashlib.sha256(template.encode()).hexdigest() != pins["serving_template_sha256"]:
        raise ValueError(
            "Serving template changed; reverify compatibility before import"
        )
    if '"""' in template:
        raise ValueError("Unexpected template delimiter")
    with httpx.Client(
        base_url="http://127.0.0.1:11434", timeout=30, trust_env=False
    ) as client:
        response = client.get("/api/tags")
        response.raise_for_status()
        before = {m["name"]: m["digest"] for m in response.json()["models"]}
        require_new_tag(tag, before)
        output.mkdir(parents=True)
        modelfile = output / "Modelfile"
        modelfile.write_text(
            f'FROM {json.dumps(str(gguf))}\nTEMPLATE """{template}"""\nPARAMETER num_ctx 16384\nPARAMETER temperature 0\nPARAMETER seed 42\n'
        )
        metadata = {
            "tag": tag,
            "gguf_sha256": digest,
            "gguf_bytes": gguf.stat().st_size,
            "template_origin": str(base.relative_to(ROOT)),
            "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
            "existing_tags_before": before,
            "status": "import_started",
        }
        provenance = output / "import.json"
        provenance.write_text(json.dumps(metadata, indent=2) + "\n")
        command = ["ollama", "create", tag, "-f", str(modelfile)]
        with (output / "import.log").open("w") as log:
            result = subprocess.run(
                command,
                env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11434"},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        metadata["command"] = command
        metadata["exit_code"] = result.returncode
        response = client.get("/api/tags")
        response.raise_for_status()
        after = {m["name"]: m["digest"] for m in response.json()["models"]}
        metadata["existing_tags_preserved"] = all(
            after.get(k) == v for k, v in before.items()
        )
        metadata["candidate_digest"] = after.get(tag)
        metadata["status"] = (
            "imported" if result.returncode == 0 and tag in after else "failed"
        )
        provenance.write_text(json.dumps(metadata, indent=2) + "\n")
        if metadata["status"] != "imported" or not metadata["existing_tags_preserved"]:
            raise RuntimeError(
                f"Import verification failed; inspect {output / 'import.log'}"
            )
    print(f"Imported {tag}; existing tags preserved. App model selection unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import_candidate(args.gguf, args.tag, args.output)
