"""Token/masking mechanics only. Builds provisional targets in memory, not a training export."""

import hashlib, json
from importlib.metadata import version
from scripts.medication_experiment import (
    DATA,
    ROOT,
    load_cases,
    request,
    validate_output,
)
from scripts.training_tokens import checked_tokens


def main():
    from transformers import AutoTokenizer

    path = ROOT / ".runtime/preparation/qwen3-1.7b-mlx4"
    tokenizer = AutoTokenizer.from_pretrained(
        path, local_files_only=True, trust_remote_code=False
    )
    expected = json.loads((DATA / "expected-facts.json").read_text())["cases"]
    report = {
        "status": "Provisional target length and completion-mask mechanics only; no training export or weights loaded",
        "tokenizer_files": {
            n: hashlib.sha256((path / n).read_bytes()).hexdigest()
            for n in ["tokenizer.json", "tokenizer_config.json"]
        },
        "versions": {n: version(n) for n in ["mlx", "mlx-lm", "transformers"]},
        "cases": [],
    }
    for case in load_cases():
        for candidate, revision in [("A", 1), ("B", 1), ("A", 2), ("B", 2)]:
            req, mapping = request(candidate, case["source_note"], revision)
            e = expected[case["case_id"]]
            if candidate == "A":
                target = e["roles"]
            else:

                def evidence(ids):
                    return [
                        {"source_unit": uid, "quote": mapping[uid]["model_text"]}
                        for uid in ids
                    ]

                target = {
                    "medications": [
                        {
                            **{
                                k: m[k]
                                for k in [
                                    "role",
                                    "name",
                                    "dose",
                                    "route",
                                    "time",
                                    "frequency",
                                ]
                            },
                            "evidence": evidence(m["units"]),
                        }
                        for m in e["medications"]
                    ],
                    "allergies": [
                        {"statement": text, "evidence": evidence([uid])}
                        for uid, text in e["allergies"].items()
                    ],
                    "medication_context": [
                        {"statement": text, "evidence": evidence([uid])}
                        for uid, text in e["context"].items()
                    ],
                }
            text = json.dumps(target, ensure_ascii=False, separators=(",", ":"))
            validated = validate_output(candidate, text, mapping)
            if not validated["evidence_valid"]:
                raise ValueError(validated["evidence_errors"])
            messages = req["messages"] + [{"role": "assistant", "content": text}]
            tokens, offset = checked_tokens(
                {"messages": messages}, tokenizer, max_length=16384
            )
            report["cases"].append(
                {
                    "case_id": case["case_id"],
                    "candidate": candidate,
                    "prompt_revision": revision,
                    "prompt_tokens": offset,
                    "completion_tokens": len(tokens) - offset,
                    "full_tokens": len(tokens),
                    "mask_prefix_and_nonthinking_verified": True,
                    "within_1600_output_tokens": len(tokens) - offset <= 1600,
                }
            )
    out = DATA / "token-mask-audit.json"
    if out.exists():
        raise FileExistsError(out)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
