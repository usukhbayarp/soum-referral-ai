"""Bounded, opt-in fictional-development experiment. Never changes serving defaults.
Captures requests/responses ONLY for bundled fictional cases, not interactive notes.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from app.adapter import OllamaAdapter, OPTIONS
from app.core import (
    ROOT,
    Contract,
    prepare,
    resolve,
    ExtractionError,
    SEGMENTATION_VERSION,
)

CONTRACT = Contract("experimental-0.6", "source-id-v06-1")
DESIGN_PATH = ROOT / "experiments/recovery-v06/grouped-source-id-v06-1.json"
DESIGN = json.loads(DESIGN_PATH.read_text())


def presentation(units):
    # Remove only an anchored original source-marker prefix, never modify units.
    return [
        {"id": u["id"], "text": re.sub(r"^\[S\d+\]\s*", "", u["text"])} for u in units
    ]


def requests(note, model, grouped):
    units, user, schema = prepare(note, CONTRACT)
    groups = DESIGN["groups"] if grouped else [list(schema["properties"])]
    result = []
    for group in groups:
        subset = copy.deepcopy(schema)
        subset["properties"] = {k: schema["properties"][k] for k in group}
        subset["required"] = group
        content = (
            json.dumps(
                {
                    "headings": {
                        f["id"]: f["label"] + ": " + f["instruction"]
                        for f in CONTRACT.fields
                        if f["id"] in group
                    },
                    "source_units": presentation(units),
                },
                ensure_ascii=False,
            )
            if grouped
            else user
        )
        result.append(
            {
                "model": model,
                "stream": False,
                "think": False,
                "format": subset,
                "keep_alive": 0,
                "options": OPTIONS,
                "messages": [
                    {
                        "role": "system",
                        "content": DESIGN["system"] if grouped else CONTRACT.system,
                    },
                    {"role": "user", "content": content},
                ],
            }
        )
    return units, result


def merge_outputs(raws, groups, units):
    """Atomic strict validation; invalid/partial groups cannot masquerade as abstentions."""
    combined = {}
    for raw, group in zip(raws, groups, strict=True):

        def unique(pairs):
            d = {}
            for k, v in pairs:
                if k in d:
                    raise ValueError("duplicate key")
                d[k] = v
            return d

        data = json.loads(raw, object_pairs_hook=unique)
        if (
            not isinstance(data, dict)
            or set(data) != set(group)
            or set(combined) & set(data)
        ):
            raise ValueError("group keys mismatch")
        combined.update(data)
    resolve(json.dumps(combined), units, CONTRACT)
    return combined


def assignment_score(expected, actual):
    if expected is None:
        return None
    return {
        k: {
            "expected": v,
            "actual": actual[k],
            "exact": set(v) == set(actual[k]),
            "missing": sorted(set(v) - set(actual[k])),
            "extra": sorted(set(actual[k]) - set(v)),
        }
        for k, v in expected.items()
    }


def fixtures():
    cases = json.loads((ROOT / "evaluation/dev002-v06/cases.json").read_text())
    older = json.loads((ROOT / "evaluation/fixtures/development.json").read_text())
    # Existing notes only. Preserve family, split and unreviewed status. No invented reference labels.
    for c in older:
        c = copy.deepcopy(c)
        c["original_schema_version"] = c["schema_version"]
        c["schema_version"] = CONTRACT.schema["version"]
        c["prompt_version"] = CONTRACT.prompt_version
        c["expected_assignments"] = None
        cases.append(c)
    assert all(
        c["split"] == "development"
        and "fictional" in c["synthetic_origin"]
        and c["clinician_review_status"] != "reviewed"
        for c in cases
    )
    return cases


async def run(model, grouped, destination, skip_dev002=False):
    adapter = OllamaAdapter(model=model)
    await adapter.readiness()
    cases = fixtures()
    if skip_dev002:
        cases = cases[1:]
    destination.mkdir(parents=True, exist_ok=False)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "quality_status": "Unreviewed development mechanics; not clinical validation",
        "prompt_version": DESIGN["version"] if grouped else CONTRACT.prompt_version,
        "schema_version": CONTRACT.schema["version"],
        "segmentation_version": SEGMENTATION_VERSION,
        "design_sha256": hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
        "cases": [],
    }
    (destination / "fixtures.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    )
    async with httpx.AsyncClient(
        base_url=adapter.base_url, trust_env=False, timeout=120
    ) as client:
        report["identity"] = (
            await client.post("/api/show", json={"model": model})
        ).json()
        report["tags"] = (await client.get("/api/tags")).json()
        report["runtime"] = (await client.get("/api/version")).json()
        for case in cases:
            started = time.perf_counter()
            units, calls = requests(case["source_note"], model, grouped)
            entry = {
                "case_id": case["case_id"],
                "source_sha256": hashlib.sha256(
                    case["source_note"].encode()
                ).hexdigest(),
                "units": units,
                "presentation": presentation(units) if grouped else units,
                "calls": [],
            }
            raws = []
            error = None
            for request in calls:
                call = {"request": request}
                start = time.perf_counter()
                try:
                    wire = client.build_request("POST", "/api/chat", json=request)
                    call["serialized_request"] = wire.content.decode()
                    response = await client.send(wire)
                    call["status"] = response.status_code
                    response.raise_for_status()
                    data = response.json()
                    call["response"] = data
                    if (
                        data.get("done") is not True
                        or data.get("done_reason") != "stop"
                    ):
                        raise ValueError("incomplete_output")
                    if data.get("message", {}).get("thinking"):
                        raise ValueError("unexpected_thinking")
                    raws.append(data["message"]["content"])
                except (httpx.HTTPError, ValueError, KeyError) as e:
                    error = str(e) or type(e).__name__
                call["latency_seconds"] = round(time.perf_counter() - start, 3)
                entry["calls"].append(call)
                # Save partial failures, retain all groups' diagnostic outputs.
            try:
                if error:
                    raise ValueError(error)
                actual = merge_outputs(
                    raws, [r["format"]["required"] for r in calls], units
                )
                entry["assignments"] = actual
                entry["score"] = assignment_score(
                    case.get("expected_assignments"), actual
                )
                entry["abstentions"] = [k for k, v in actual.items() if not v]
            except (ValueError, TypeError, ExtractionError) as e:
                error = str(e) or type(e).__name__
                entry["abstentions"] = None
            entry["validation_error"] = error
            entry["latency_seconds"] = round(time.perf_counter() - started, 3)
            report["cases"].append(entry)
            (destination / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            print(
                model,
                entry["case_id"],
                entry["latency_seconds"],
                error or "valid",
                flush=True,
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=["qwen3:1.7b", "qwen3:4b"], required=True)
    p.add_argument("--grouped", action="store_true")
    p.add_argument("--skip-dev002", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    asyncio.run(run(a.model, a.grouped, a.output, a.skip_dev002))
