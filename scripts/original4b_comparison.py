"""Run frozen medication A/B prompts against a separately pinned original 4B tag.
No experiment prompts, schemas, validation, request budgets or 1.7B results change.
"""

import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path
import httpx
from scripts import medication_experiment as frozen

TAG = "soum-qwen3-4b-original:q4_k_m-bc640142"
OUT = frozen.ROOT / "evaluation/original4b-v07"


async def sample_memory(stop, samples):
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", trust_env=False, timeout=5
    ) as client:
        while not stop.is_set():
            sample = {"monotonic_seconds": time.monotonic()}
            try:
                sample["ollama_ps"] = (await client.get("/api/ps")).json()
                # Only process name and RSS, never command arguments or environment.
                proc = await asyncio.create_subprocess_exec(
                    "ps", "-axo", "pid=,rss=,comm=", stdout=asyncio.subprocess.PIPE
                )
                data, _ = await proc.communicate()
                sample["ollama_rss_kib"] = [
                    s.strip()
                    for s in data.decode().splitlines()
                    if "ollama" in s.lower()
                ]
            except Exception as exc:
                sample["error"] = type(exc).__name__
            samples.append(sample)
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except TimeoutError:
                pass


async def run():
    identity = json.loads((OUT / "import/import.json").read_text())
    assert identity["tag"] == TAG and identity["existing_tags_preserved"]
    # Module globals only in this isolated process. Frozen request factory/run/validator reused verbatim.
    frozen.MODEL = TAG
    frozen.DIGEST = identity["candidate_digest"]
    stop = asyncio.Event()
    samples = []
    task = asyncio.create_task(sample_memory(stop, samples))
    before = subprocess.check_output(["memory_pressure"], text=True)
    try:
        for revision in (1, 2):
            await frozen.run(OUT / f"run-v{revision}", revision)
    finally:
        stop.set()
        await task
        (OUT / "memory.json").write_text(
            json.dumps(
                {
                    "method": "2-second sampled Ollama process RSS (KiB) and /api/ps size_vram; not additive, not a precise physical GPU allocation peak",
                    "system_before": before,
                    "system_after": subprocess.check_output(
                        ["memory_pressure"], text=True
                    ),
                    "samples": samples,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(run())
