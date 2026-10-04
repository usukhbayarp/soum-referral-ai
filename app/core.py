"""Pure source segmentation and strict evidence resolution; no model-generated prose."""

import os
import copy
import json
import re
from pathlib import Path
from pydantic import ConfigDict, StrictInt, create_model

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "config/referral.v0.1.json").read_text())
PROMPT_VERSION = os.getenv("EXTRACTION_PROMPT_VERSION", "source-id-2")
if PROMPT_VERSION not in ("source-id-1", "source-id-2"):
    raise ValueError("Unknown versioned extraction prompt")
MAX_CHARS = 3000
MAX_UNITS = 80
FIELDS = tuple(f for f in SCHEMA["fields"] if not f["manual"])
Assignment = create_model(
    "Assignment",
    __config__=ConfigDict(extra="forbid", strict=True),
    **{f["id"]: (list[StrictInt], ...) for f in FIELDS},
)
SEGMENTATION_VERSION = "sentence-lines-1"
OUTPUT_SCHEMA_VERSION = "source-id-1"
SYSTEM = (ROOT / f"config/extraction.{PROMPT_VERSION}.txt").read_text().strip()
OUTPUT_SCHEMA = json.loads((ROOT / "config/output.source-id-1.json").read_text())


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


def prepare(note):
    if not note.strip() or len(note) > MAX_CHARS:
        raise ExtractionError("input_limit", 413)
    units = segment(note)
    payload = {
        "headings": {
            f["id"]: (f["label"] + ": " if PROMPT_VERSION == "source-id-2" else "")
            + f["instruction"]
            for f in FIELDS
        },
        "source_units": units,
    }
    user = json.dumps(payload, ensure_ascii=False)
    # Conservative UTF-8 byte bound below context budget, including template overhead and output.
    if len((SYSTEM + user).encode("utf-8")) > 12000:
        raise ExtractionError("input_limit", 413)
    schema = copy.deepcopy(OUTPUT_SCHEMA)
    for prop in schema["properties"].values():
        prop["items"] = {"type": "integer", "enum": [u["id"] for u in units]}
        prop["maxItems"] = len(units)
        prop["uniqueItems"] = True
    return units, user, schema


def resolve(raw: str, units: list[dict]):
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
        assignments = Assignment.model_validate(data).model_dump()
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
        return result
    except (ValueError, TypeError):
        raise ExtractionError() from None
