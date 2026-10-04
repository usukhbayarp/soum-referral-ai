"""Explicitly saves ONLY the bundled fictional development fixtures' model outputs."""

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import time
import httpx
from app.adapter import OllamaAdapter, OPTIONS
from app.core import (
    ROOT,
    SCHEMA,
    PROMPT_VERSION,
    OUTPUT_SCHEMA_VERSION,
    SEGMENTATION_VERSION,
    ExtractionError,
)


async def run(models, destination):
    probe = OllamaAdapter(model=models[0])
    cases_path = ROOT / "evaluation/fixtures/development.json"
    cases = json.loads(cases_path.read_text())
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "quality_status": "UNREVIEWED: mechanics only, no clinical accuracy score",
        "fixture_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "schema_version": SCHEMA["version"],
        "prompt_version": PROMPT_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "segmentation_version": SEGMENTATION_VERSION,
        "settings": {"think": False, "stream": False, "keep_alive": 0, **OPTIONS},
        "inference_timeout_seconds": probe.timeout,
        "contract_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "config").glob("*"))
        },
        "models": [],
    }
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = destination / f"comparison-{stamp}.json"
    async with httpx.AsyncClient(
        base_url=probe.base_url, trust_env=False, timeout=30
    ) as client:
        report["runtime"] = (await client.get("/api/version")).json()
        tags = (await client.get("/api/tags")).json()["models"]
        for model in models:
            metadata = next((m for m in tags if m["name"] == model), None)
            show = await client.post("/api/show", json={"model": model})
            shown = show.json() if show.status_code == 200 else {}
            entry = {
                "identifier": model,
                "metadata": metadata,
                "capabilities": shown.get("capabilities"),
                "model_info": shown.get("model_info"),
                "runtime_parameters": shown.get("parameters"),
                "template_sha256": hashlib.sha256(
                    shown.get("template", "").encode()
                ).hexdigest(),
                "template": shown.get("template"),
                "thinking_capabilities": {
                    k: v for k, v in shown.items() if "think" in k
                },
                "cases": [],
            }
            report["models"].append(entry)
            adapter = OllamaAdapter(model=model)
            for case in cases:
                assert (
                    case["split"] == "development"
                    and "fictional" in case["synthetic_origin"]
                )
                start = time.perf_counter()
                result = {
                    "case_id": case["case_id"],
                    "clinician_review_status": case["clinician_review_status"],
                }
                try:
                    result["output"] = await adapter.extract(
                        case["source_note"], capture=True
                    )
                    result["validation_error"] = None
                    result["abstentions"] = [
                        k
                        for k, v in result["output"]["fields"].items()
                        if v["status"] == "not_found"
                    ]
                except ExtractionError as error:
                    result["validation_error"] = error.code
                    result["raw_output"] = getattr(error, "raw_output", None)
                    result["abstentions"] = (
                        None  # Failure is never counted as an abstention.
                    )
                result["latency_seconds"] = round(time.perf_counter() - start, 3)
                entry["cases"].append(result)
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                print(
                    model,
                    case["case_id"],
                    result["latency_seconds"],
                    result["validation_error"] or "valid",
                    flush=True,
                )
            # Explicitly unload this candidate before advancing to the next model.
            await client.post("/api/generate", json={"model": model, "keep_alive": 0})
    print("Saved", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["qwen3:1.7b", "qwen3:4b"])
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/results")
    args = parser.parse_args()
    asyncio.run(run(args.models, args.output))
