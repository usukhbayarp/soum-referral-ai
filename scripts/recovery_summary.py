"""Summarize saved fictional results only; never calls a model or alters raw outputs."""

import json
from pathlib import Path
from scripts.recovery import ROOT, assignment_score

D = ROOT / "evaluation/recovery-v06"


def read(path):
    return json.loads(path.read_text())


def summarize():
    expected = read(ROOT / "evaluation/dev002-v06/cases.json")[0][
        "expected_assignments"
    ]
    old = read(ROOT / "evaluation/dev002-v06/results/comparison-20261004T071312Z.json")[
        "models"
    ][0]["cases"][0]
    first4 = read(D / "baseline-4b-dev002.json")
    grouped = read(D / "grouped-1.7b/report.json")
    entries = [
        (
            "baseline-1.7b",
            "source-id-v06-1",
            json.loads(old["output"]["raw_output"]),
            old["latency_seconds"],
            old["validation_error"],
            True,
        ),
        (
            "baseline-4b",
            "source-id-v06-1",
            json.loads(first4["output"]["raw_output"]),
            first4["latency_seconds"],
            first4["error"],
            False,
        ),
        (
            "grouped-1.7b",
            "grouped-source-id-v06-1",
            grouped["cases"][0].get("assignments"),
            grouped["cases"][0]["latency_seconds"],
            grouped["cases"][0]["validation_error"],
            False,
        ),
    ]
    report = {
        "status": "Unreviewed provisional assignment comparisons, not clinical accuracy. Counts are field-ID pairs, not unique source units.",
        "DEV-002": [],
        "other_development": [],
    }
    for name, prompt, actual, seconds, error, historical in entries:
        score = assignment_score(expected, actual) if actual is not None else None
        report["DEV-002"].append(
            {
                "candidate": name,
                "prompt_version": prompt,
                "historical_output_reused": historical,
                "validation_error": error,
                "latency_seconds": round(seconds, 3),
                "exact_field_sets": (
                    sum(v["exact"] for v in score.values()) if score else None
                ),
                "missing_assignment_pairs": (
                    sum(len(v["missing"]) for v in score.values()) if score else None
                ),
                "extra_assignment_pairs": (
                    sum(len(v["extra"]) for v in score.values()) if score else None
                ),
                "abstentions": (
                    [k for k, v in actual.items() if not v] if actual else None
                ),
                "fields": score,
            }
        )
    for name in ["baseline-1.7b-other", "baseline-4b-other", "grouped-1.7b"]:
        path = D / name / "report.json"
        if not path.exists():
            continue
        for c in read(path)["cases"]:
            if c["case_id"] == "DEV-002":
                continue
            report["other_development"].append(
                {
                    "candidate": name,
                    "case_id": c["case_id"],
                    "validation_error": c["validation_error"],
                    "latency_seconds": c["latency_seconds"],
                    "abstentions": c["abstentions"],
                    "missing_extra": "Unavailable: no expected v0.6 labels for this existing case. Qualitative audit only.",
                }
            )
    out = D / "summary.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for c in report["DEV-002"]:
        print(
            c["candidate"],
            c["latency_seconds"],
            "exact",
            c["exact_field_sets"],
            "missing",
            c["missing_assignment_pairs"],
            "extra",
            c["extra_assignment_pairs"],
            "abstentions",
            c["abstentions"],
        )


if __name__ == "__main__":
    summarize()
