"""Isolated fictional-development representation experiment; never serves or trains."""

import argparse, asyncio, hashlib, json, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, create_model
from app.core import ROOT, segment
from app.adapter import OllamaAdapter

DIR = ROOT / "experiments/medication-v1"
DATA = ROOT / "evaluation/medication-v1"
MODEL = "qwen3:1.7b"
DIGEST = "8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7"
SETTINGS = {"temperature": 0, "seed": 42, "num_ctx": 16384, "num_predict": 1600}
ROLES = json.loads((DIR / "roles.json").read_text())


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Detail = Annotated[str, Field(min_length=1, max_length=500)]
Text = Annotated[str, Field(min_length=1, max_length=3000)]


class Evidence(StrictModel):
    source_unit: str
    quote: Text


EvidenceList = Annotated[list[Evidence], Field(min_length=1, max_length=12)]


class Medication(StrictModel):
    role: Literal[
        "regular_medication",
        "administered_treatment",
        "historical_medication",
        "planned_or_prescribed_treatment",
        "explicitly_not_administered",
        "mixed_or_unclear",
    ]
    name: Detail
    dose: Detail | None
    route: Detail | None
    time: Detail | None
    frequency: Detail | None
    evidence: EvidenceList


class Statement(StrictModel):
    statement: Text
    evidence: EvidenceList


class Structured(StrictModel):
    medications: Annotated[list[Medication], Field(max_length=16)]
    allergies: Annotated[list[Statement], Field(max_length=16)]
    medication_context: Annotated[list[Statement], Field(max_length=16)]


def model_view(note):
    units = segment(note)
    paragraphs = []
    mapping = {}
    # Paragraph grouping uses original newline boundaries, no clinical headings.
    for unit in units:
        uid = f"U{unit['id']}"
        paragraph = note[: unit["start"]].count("\n")
        while len(paragraphs) <= paragraph:
            paragraphs.append([])
        text = re.sub(r"^\[S\d+\]\s*", "", unit["text"])
        paragraphs[paragraph].append({"id": uid, "text": text})
        mapping[uid] = {**unit, "model_text": text}
    return {"paragraphs": paragraphs}, mapping


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def schema(candidate, ids):
    if candidate == "A":
        return object_schema(
            {uid: {"type": "string", "enum": list(ROLES)} for uid in ids}
        )
    evidence = {
        "type": "array",
        "minItems": 1,
        "maxItems": 12,
        "items": object_schema(
            {
                "source_unit": {"type": "string", "enum": list(ids)},
                "quote": {"type": "string", "minLength": 1, "maxLength": 3000},
            }
        ),
    }
    statement = object_schema(
        {
            "statement": {"type": "string", "minLength": 1, "maxLength": 3000},
            "evidence": evidence,
        }
    )
    med = object_schema(
        {
            "role": {
                "type": "string",
                "enum": [r for r in ROLES if r not in ["allergy_statement", "other"]],
            },
            "name": {"type": "string", "minLength": 1, "maxLength": 500},
            **{
                k: {"type": ["string", "null"], "minLength": 1, "maxLength": 500}
                for k in ["dose", "route", "time", "frequency"]
            },
            "evidence": evidence,
        }
    )
    return object_schema(
        {
            "medications": {"type": "array", "maxItems": 16, "items": med},
            "allergies": {"type": "array", "maxItems": 16, "items": statement},
            "medication_context": {"type": "array", "maxItems": 16, "items": statement},
        }
    )


def request(candidate, note, revision=1):
    view, mapping = model_view(note)
    prompt_dir = ROOT / f"experiments/medication-v{revision}"
    payload = {
        "role_definitions": json.loads((prompt_dir / "roles.json").read_text()),
        **view,
    }
    return {
        "model": MODEL,
        "stream": False,
        "think": False,
        "keep_alive": "5m",
        "options": SETTINGS,
        "format": schema(candidate, mapping),
        "messages": [
            {
                "role": "system",
                "content": (prompt_dir / f"{candidate}.txt").read_text().strip(),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }, mapping


def strict_json(raw):
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError("duplicate_key")
            d[k] = v
        return d

    return json.loads(raw, object_pairs_hook=unique)


def validate_envelope(data):
    if (
        not isinstance(data, dict)
        or data.get("done") is not True
        or data.get("done_reason") != "stop"
    ):
        raise ValueError("incomplete_output")
    if data.get("message", {}).get("thinking"):
        raise ValueError("unexpected_thinking")
    raw = data.get("message", {}).get("content")
    if not isinstance(raw, str):
        raise ValueError("invalid_response")
    return raw


def quote_locations(evidence, mapping):
    locations = []
    errors = []
    flags = []
    for e in evidence:
        unit = mapping[e["source_unit"]]
        quote = e["quote"]
        positions = []
        start = 0
        while True:
            pos = unit["text"].find(quote, start)
            if pos < 0:
                break
            positions.append(
                {"start": unit["start"] + pos, "end": unit["start"] + pos + len(quote)}
            )
            start = pos + 1
        if not positions:
            errors.append({"type": "quote_mismatch", "evidence": e})
        if len(positions) > 1:
            flags.append(
                {
                    "type": "ambiguous_repeated_quote",
                    "evidence": e,
                    "locations": positions,
                }
            )
        locations.append(
            {"source_unit": e["source_unit"], "quote": quote, "locations": positions}
        )
    return locations, errors, flags


def validate_output(candidate, raw, mapping):
    data = strict_json(raw)
    if candidate == "A":
        model = create_model(
            "UnitRoles",
            __config__=ConfigDict(extra="forbid", strict=True),
            **{uid: (Literal[tuple(ROLES)], ...) for uid in mapping},
        )
        model.model_validate(data)
    else:
        Structured.model_validate(data)
        for kind in ["medications", "allergies", "medication_context"]:
            for item in data[kind]:
                if any(e["source_unit"] not in mapping for e in item["evidence"]):
                    raise ValueError("unknown_source_unit")
    if candidate == "A":
        groups = {
            role: [
                {"source_unit": uid, **mapping[uid]}
                for uid, r in data.items()
                if r == role
            ]
            for role in ROLES
        }
        return {
            "structural_valid": True,
            "evidence_valid": True,
            "output": data,
            "groups": groups,
            "review_flags": [
                {"source_unit": uid, "type": "mixed_or_unclear_requires_review"}
                for uid, r in data.items()
                if r == "mixed_or_unclear"
            ],
            "evidence_errors": [],
            "semantic_validation": "Not performed; wrong roles/other omissions require external checklist audit.",
        }
    result = {
        "structural_valid": True,
        "output": data,
        "evidence_errors": [],
        "review_flags": [],
        "resolved_evidence": [],
    }
    for kind in ["medications", "allergies", "medication_context"]:
        for i, entry in enumerate(data[kind]):
            locations, errs, flags = quote_locations(entry["evidence"], mapping)
            result["resolved_evidence"].append(
                {"kind": kind, "index": i, "spans": locations}
            )
            result["evidence_errors"] += [{"kind": kind, "index": i, **e} for e in errs]
            result["review_flags"] += [{"kind": kind, "index": i, **f} for f in flags]
            keys = (
                ["name", "dose", "route", "time", "frequency"]
                if kind == "medications"
                else ["statement"]
            )
            for key in keys:
                value = entry[key]
                if value is not None and not any(
                    value in e["quote"] for e in entry["evidence"]
                ):
                    result["evidence_errors"].append(
                        {
                            "kind": kind,
                            "index": i,
                            "type": "detail_not_in_linked_quote",
                            "detail": key,
                            "value": value,
                        }
                    )
            if kind != "medications":
                # Entire unit wording, with only annotation-prefix removal permitted.
                if entry["statement"] not in [
                    mapping[e["source_unit"]]["model_text"] for e in entry["evidence"]
                ]:
                    result["evidence_errors"].append(
                        {"kind": kind, "index": i, "type": "statement_not_intact_unit"}
                    )
            else:
                # Always flag associations. Lexical co-occurrence can never prove them.
                result["review_flags"].append(
                    {
                        "kind": kind,
                        "index": i,
                        "type": "drug_detail_role_association_requires_review",
                    }
                )
                if len(set(e["source_unit"] for e in entry["evidence"])) > 1:
                    result["review_flags"].append(
                        {
                            "kind": kind,
                            "index": i,
                            "type": "cross_unit_association_requires_review",
                        }
                    )
                if entry["role"] == "mixed_or_unclear":
                    result["review_flags"].append(
                        {
                            "kind": kind,
                            "index": i,
                            "type": "unclear_role_requires_review",
                        }
                    )
    result["evidence_valid"] = not result["evidence_errors"]
    result["semantic_validation"] = (
        "Not performed. Even exact quotes can support the wrong drug/role/time association; no automatic acceptance."
    )
    return result


def load_cases():
    cases = json.loads((DATA / "cases.json").read_text())
    if not all(
        c["split"] == "development"
        and c["clinician_review_status"] == "unreviewed"
        and "fictional" in c["synthetic_origin"]
        for c in cases
    ):
        raise ValueError("Only fixed fictional unreviewed development cases permitted")
    return cases


async def run(destination, revision=1):
    prompt_dir = ROOT / f"experiments/medication-v{revision}"
    cases = load_cases()
    destination.mkdir(parents=True, exist_ok=False)
    adapter = OllamaAdapter(model=MODEL)
    await adapter.readiness()
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "model": MODEL,
        "pinned_digest": DIGEST,
        "settings": {"think": False, "stream": False, "keep_alive": "5m", **SETTINGS},
        "request_timeout_seconds": 60,
        "contract": "medication-representation-1",
        "prompt_revision": revision,
        "hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                prompt_dir / "A.txt",
                prompt_dir / "B.txt",
                prompt_dir / "roles.json",
                DATA / "cases.json",
                DATA / "expected-facts.json",
                Path(__file__),
            ]
        },
        "runs": [],
    }
    async with httpx.AsyncClient(
        base_url=adapter.base_url, trust_env=False, timeout=60
    ) as client:
        tags = (await client.get("/api/tags")).json()["models"]
        local = next(m for m in tags if m["name"] == MODEL)
        if local["digest"] != DIGEST:
            raise ValueError("model_digest_changed")
        report["identity"] = (
            await client.post("/api/show", json={"model": MODEL})
        ).json()
        report["runtime"] = (await client.get("/api/version")).json()
        report["loaded_before"] = (await client.get("/api/ps")).json()
        # One cold-first pair, alternating order thereafter; repeat DEV-002 once per candidate.
        sequence = []
        for i, c in enumerate(cases):
            for candidate in ["A", "B"] if i % 2 == 0 else ["B", "A"]:
                sequence.append((candidate, c, False))
        if revision == 1:
            sequence += [("A", cases[0], True), ("B", cases[0], True)]
        for candidate, case, repeat in sequence:
            req, mapping = request(candidate, case["source_note"], revision)
            wire = client.build_request("POST", "/api/chat", json=req)
            entry = {
                "candidate": candidate,
                "prompt_version": f"medication-{candidate}-{revision}",
                "case_id": case["case_id"],
                "repeat": repeat,
                "request": req,
                "serialized_request": wire.content.decode(),
                "original_source": case["source_note"],
                "source_mapping": mapping,
            }
            entry["loaded_before"] = (await client.get("/api/ps")).json()
            start = time.perf_counter()
            try:
                async with asyncio.timeout(60):
                    response = await client.send(wire)
                    entry["status"] = response.status_code
                    entry["raw_response"] = response.text
                    response.raise_for_status()
                    envelope = response.json()
                    entry["response"] = envelope
                    raw = validate_envelope(envelope)
                    entry["validation"] = validate_output(candidate, raw, mapping)
                    entry["error"] = None
            except (
                ValueError,
                TypeError,
                KeyError,
                httpx.HTTPError,
                TimeoutError,
            ) as e:
                entry["error"] = str(e) or type(e).__name__
                entry["validation"] = None
            entry["wall_seconds"] = round(time.perf_counter() - start, 3)
            report["runs"].append(entry)
            (destination / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            print(
                candidate,
                case["case_id"],
                "repeat" if repeat else "first",
                entry["wall_seconds"],
                entry["error"]
                or (
                    "lexical-valid"
                    if entry["validation"]["evidence_valid"]
                    else "evidence-invalid"
                ),
                flush=True,
            )
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (destination / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    # No unload: only the requested 5-minute residency expires normally.


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--revision", type=int, choices=[1, 2], default=1)
    args = p.parse_args()
    asyncio.run(run(args.output, args.revision))
