"""Validate canonical labels; export reviewed synthetic train/dev only. No MLX dependency."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, StrictInt
from app.core import (
    Contract,
    SEGMENTATION_VERSION,
    ExtractionError,
    prepare,
    resolve,
    ROOT,
)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str = Field(min_length=1, max_length=128)
    underlying_case_id: str = Field(min_length=1, max_length=128)
    source_note: str = Field(min_length=1, max_length=3000)
    expected_assignments: dict[str, list[StrictInt]] | None
    prompt_version: str | None = None
    schema_version: str
    segmentation_version: str
    split: Literal["train", "development", "test"]
    synthetic_origin: str = Field(min_length=1)
    clinician_review_status: Literal["unreviewed", "reviewed", "rejected"]
    scenario: str = ""


def validate_cases(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Dataset must be a nonempty JSON array")
    cases, ids, underlying, note_splits = [], set(), {}, {}
    for index, record in enumerate(records):
        try:
            case = Case.model_validate(record)
        except ValidationError:
            raise ValueError(
                f"Case at index {index}: invalid canonical structure (content omitted)"
            ) from None
        if case.case_id in ids:
            raise ValueError("Duplicate case_id")
        ids.add(case.case_id)
        if case.segmentation_version != SEGMENTATION_VERSION:
            raise ValueError("Schema or segmentation version mismatch")
        contract = Contract(case.schema_version, case.prompt_version)
        if case.schema_version == "experimental-0.6" and case.prompt_version is None:
            raise ValueError("v0.6 requires explicit prompt_version")
        if (
            case.case_id.startswith("DEV-002") or "DEV-002" in case.source_note
        ) and case.underlying_case_id != "DEV-002":
            raise ValueError("DEV-002 variants must share underlying_case_id DEV-002")
        if case.underlying_case_id == "DEV-002" and case.split != "development":
            raise ValueError("DEV-002 family is development-only")
        prior = underlying.setdefault(case.underlying_case_id, case.split)
        if prior != case.split:
            raise ValueError("Underlying-case overlap across splits")
        digest = hashlib.sha256(case.source_note.strip().encode()).hexdigest()
        if note_splits.setdefault(digest, case.split) != case.split:
            raise ValueError("Exact source-note overlap across splits")
        try:
            units, _, _ = prepare(case.source_note, contract)
            if case.expected_assignments is not None:
                resolve(json.dumps(case.expected_assignments), units, contract)
        except ExtractionError:
            raise ValueError(
                "Source limits or expected evidence assignments invalid"
            ) from None
        if (
            case.clinician_review_status == "reviewed"
            and case.expected_assignments is None
        ):
            raise ValueError("Reviewed cases require complete explicit labels")
        cases.append(case)
    return cases


def export_cases(cases, destination):
    selected = [
        c
        for c in cases
        if c.split in ("train", "development")
        and c.clinician_review_status == "reviewed"
    ]
    if not selected:
        raise ValueError("No reviewed train/development cases; nothing exported")
    versions = {(c.schema_version, c.prompt_version) for c in selected}
    if len(versions) != 1:
        raise ValueError("Cannot mix extraction contracts in a training export")
    contract = Contract(*next(iter(versions)))
    # Caller supplies all splits for leakage checking. Never reuse an old output directory.
    if destination.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    destination.mkdir(parents=True)
    manifest = {
        "format": "mlx-lm-0.30.7-chat-jsonl",
        "schema_version": contract.schema["version"],
        "segmentation_version": SEGMENTATION_VERSION,
        "prompt_version": contract.prompt_version,
        "output_schema_version": contract.output_version,
        "cases": [],
        "contract_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "config").glob("*"))
        },
    }
    for split, filename in [("train", "train.jsonl"), ("development", "valid.jsonl")]:
        lines = []
        for case in selected:
            if case.split != split:
                continue
            _, user, _ = prepare(case.source_note, contract)
            messages = [
                {"role": "system", "content": contract.system},
                {"role": "user", "content": user},
                {
                    "role": "assistant",
                    "content": json.dumps(
                        case.expected_assignments, ensure_ascii=False
                    ),
                },
            ]
            lines.append(json.dumps({"messages": messages}, ensure_ascii=False))
            manifest["cases"].append(
                {
                    "case_id": case.case_id,
                    "underlying_case_id": case.underlying_case_id,
                    "split": split,
                }
            )
        # MLX 0.30.7 attempts to inspect data[0] for an existing file, so omit empty splits.
        if lines:
            (destination / filename).write_text("\n".join(lines) + "\n")
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return len(selected)


def main():
    parser = argparse.ArgumentParser(
        description="Supply the full canonical dataset including all splits to check leakage."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--export-mlx", type=Path)
    args = parser.parse_args()
    try:
        cases = validate_cases(json.loads(args.input.read_text()))
        print(
            f'Validated {len(cases)} cases; reviewed: {sum(c.clinician_review_status=="reviewed" for c in cases)}'
        )
        if args.export_mlx:
            print(f"Exported {export_cases(cases,args.export_mlx)} reviewed cases")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Validation/export failed: {error}\n")


if __name__ == "__main__":
    main()
