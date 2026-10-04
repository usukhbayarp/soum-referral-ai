"""Compare saved mechanics on identical cases/settings; never score clinical quality."""

import argparse
import json
from pathlib import Path
from statistics import mean


def compare(baseline, candidate, baseline_model, candidate_model):
    for key in (
        "fixture_sha256",
        "schema_version",
        "prompt_version",
        "output_schema_version",
        "segmentation_version",
        "settings",
        "contract_sha256",
    ):
        if baseline[key] != candidate[key]:
            raise ValueError(f"Comparison contract mismatch: {key}")
    left = next(m for m in baseline["models"] if m["identifier"] == baseline_model)
    right = next(m for m in candidate["models"] if m["identifier"] == candidate_model)
    a = {c["case_id"]: c for c in left["cases"]}
    b = {c["case_id"]: c for c in right["cases"]}
    if (
        a.keys() != b.keys()
        or len(a) != len(left["cases"])
        or len(b) != len(right["cases"])
    ):
        raise ValueError("Comparison cases differ or contain duplicate IDs")
    rows = []
    for case_id in a:
        x, y = a[case_id], b[case_id]
        both_valid = not x["validation_error"] and not y["validation_error"]
        rows.append(
            {
                "case_id": case_id,
                "baseline_error": x["validation_error"],
                "candidate_error": y["validation_error"],
                "baseline_abstentions": x["abstentions"],
                "candidate_abstentions": y["abstentions"],
                "assignment_agreement": (
                    json.loads(x["output"]["raw_output"])
                    == json.loads(y["output"]["raw_output"])
                    if both_valid
                    else None
                ),
                "baseline_seconds": x["latency_seconds"],
                "candidate_seconds": y["latency_seconds"],
                "baseline_prompt_tokens": x.get("output", {})
                .get("metrics", {})
                .get("prompt_eval_count"),
                "candidate_prompt_tokens": y.get("output", {})
                .get("metrics", {})
                .get("prompt_eval_count"),
            }
        )
    return {
        "purpose": "unreviewed fictional mechanics comparison; agreement is NOT clinical correctness",
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "same_template": left["template_sha256"] == right["template_sha256"],
        "baseline_template_sha256": left["template_sha256"],
        "candidate_template_sha256": right["template_sha256"],
        "baseline_runtime": baseline["runtime"],
        "candidate_runtime": candidate["runtime"],
        "baseline_model_info": left["model_info"],
        "candidate_model_info": right["model_info"],
        "baseline_invalid": sum(bool(x["validation_error"]) for x in a.values()),
        "candidate_invalid": sum(bool(x["validation_error"]) for x in b.values()),
        "baseline_mean_seconds": mean(x["latency_seconds"] for x in a.values()),
        "candidate_mean_seconds": mean(x["latency_seconds"] for x in b.values()),
        "cases": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--baseline-model", default="qwen3:1.7b")
    parser.add_argument("--candidate-model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        json.loads(args.baseline.read_text()),
        json.loads(args.candidate.read_text()),
        args.baseline_model,
        args.candidate_model,
    )
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved mechanics comparison to {args.output}")
