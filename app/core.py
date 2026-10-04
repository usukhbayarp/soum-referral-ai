"""Pure source segmentation and strict evidence resolution; no model-generated prose."""

import os
import copy
import json
import re
from pathlib import Path
from pydantic import ConfigDict, StrictInt, create_model

ROOT = Path(__file__).resolve().parents[1]


class Contract:
    """Explicit version selection shared by serving, validation, export and evaluation."""

    def __init__(self, version, prompt_version=None):
        if version not in ("provisional-0.1", "experimental-0.6"):
            raise ValueError("Unknown schema version")
        modern = version == "experimental-0.6"
        allowed = (
            ("source-id-v06-1", "source-id-v06-2")
            if modern
            else ("source-id-1", "source-id-2")
        )
        self.prompt_version = prompt_version or (allowed[0] if modern else allowed[-1])
        if self.prompt_version not in allowed:
            raise ValueError("Incompatible schema/prompt versions")
        self.schema = json.loads(
            (
                ROOT
                / (
                    "config/referral.v0.6.json"
                    if modern
                    else "config/referral.v0.1.json"
                )
            ).read_text()
        )
        self.output_version = "source-id-v06-1" if modern else "source-id-1"
        self.fields = tuple(f for f in self.schema["fields"] if not f["manual"])
        self.assignment = create_model(
            "Assignment",
            __config__=ConfigDict(extra="forbid", strict=True),
            **{f["id"]: (list[StrictInt], ...) for f in self.fields},
        )
        self.system = (
            (ROOT / f"config/extraction.{self.prompt_version}.txt").read_text().strip()
        )
        self.output_schema = json.loads(
            (ROOT / f"config/output.{self.output_version}.json").read_text()
        )


CONTRACT = Contract(
    os.getenv("REFERRAL_SCHEMA_VERSION", "experimental-0.6"),
    os.getenv("EXTRACTION_PROMPT_VERSION"),
)
SCHEMA = CONTRACT.schema
PROMPT_VERSION = CONTRACT.prompt_version
OUTPUT_SCHEMA_VERSION = CONTRACT.output_version
FIELDS = CONTRACT.fields
Assignment = CONTRACT.assignment
SYSTEM = CONTRACT.system
OUTPUT_SCHEMA = CONTRACT.output_schema
MAX_CHARS = 3000
MAX_UNITS = 80
SEGMENTATION_VERSION = "sentence-lines-1"


class ExtractionError(Exception):
    def __init__(self, code="invalid_evidence", status=502):
        self.code, self.status = code, status
        super().__init__(code)


def segment(note: str) -> list[dict]:
    # Split at newline or sentence-ending punctuation followed by whitespace/end.
    # Decimal points in doses are retained. Boundaries are deterministic, not clinical parsing.
    units, start = [], 0
    for match in re.finditer(r"\r?\n|[.!?](?=\s|$)", note):
        end = match.start() if "\n" in match.group() else match.end()
        _unit(note, start, end, units)
        start = match.end()
    _unit(note, start, len(note), units)
    if len(units) > MAX_UNITS:
        raise ExtractionError("too_many_units", 413)
    return units


def _unit(note, start, end, units):
    while start < end and note[start].isspace():
        start += 1
    while end > start and note[end - 1].isspace():
        end -= 1
    if start < end:
        units.append(
            {"id": len(units) + 1, "start": start, "end": end, "text": note[start:end]}
        )


def prepare(note, contract=CONTRACT):
    if not note.strip() or len(note) > MAX_CHARS:
        raise ExtractionError("input_limit", 413)
    units = segment(note)
    payload = {
        "headings": {
            f["id"]: (
                f["label"] + ": "
                if contract.prompt_version in ("source-id-2", "source-id-v06-2")
                else ""
            )
            + f["instruction"]
            for f in contract.fields
        },
        "source_units": units,
    }
    user = json.dumps(payload, ensure_ascii=False)
    # Conservative UTF-8 byte bound below context budget, including template overhead and output.
    if len((contract.system + user).encode("utf-8")) > 12000:
        raise ExtractionError("input_limit", 413)
    schema = copy.deepcopy(contract.output_schema)
    for prop in schema["properties"].values():
        prop["items"] = {"type": "integer", "enum": [u["id"] for u in units]}
        prop["maxItems"] = len(units)
        prop["uniqueItems"] = True
    return units, user, schema


def resolve(raw: str, units: list[dict], contract=CONTRACT):
    try:
        # Reject duplicate keys instead of silently taking the last value.
        def unique(pairs):
            out = {}
            for key, value in pairs:
                if key in out:
                    raise ValueError("duplicate")
                out[key] = value
            return out

        data = json.loads(raw, object_pairs_hook=unique)
        assignments = contract.assignment.model_validate(data).model_dump()
        by_id = {u["id"]: u for u in units}
        result = {}
        for field, ids in assignments.items():
            if len(ids) != len(set(ids)) or any(i not in by_id for i in ids):
                raise ValueError("invalid ID")
            evidence = [by_id[i] for i in sorted(ids)]
            result[field] = {
                "status": "extracted" if evidence else "not_found",
                "text": "\n".join(u["text"] for u in evidence),
                "evidence": evidence,
            }
        # Detect only structural reuse, not semantic truth. Keep all source text visible.
        for left, right in (
            ("initial_source", "current_source"),
            ("regular_medication", "treatment_source"),
        ):
            if (
                left in assignments
                and right in assignments
                and set(assignments[left]) & set(assignments[right])
            ):
                for name in (left, right):
                    result[name]["review_flags"] = [
                        "Эхийг хоёр өөр бүлэгт давхар сонгосон — хугацаа / эмийн хэрэглээг эмч ялгана. Утгыг автоматаар нэгтгээгүй."
                    ]
        return result
    except (ValueError, TypeError):
        raise ExtractionError() from None
