"""Build a static clinician review sheet and mechanical summaries from saved outputs only."""

import html, json, hashlib
from pathlib import Path
from scripts.medication_experiment import DATA, load_cases


def main():
    cases = load_cases()
    expected = json.loads((DATA / "expected-facts.json").read_text())["cases"]
    reports = [json.loads((DATA / f"run-v{n}/report.json").read_text()) for n in [1, 2]]
    rows = []
    for revision, report in enumerate(reports, 1):
        for run in report["runs"]:
            v = run["validation"]
            response = run.get("response", {})
            row = {
                "revision": revision,
                "candidate": run["candidate"],
                "case_id": run["case_id"],
                "repeat": run["repeat"],
                "error": run["error"],
                "structural_valid": bool(v),
                "evidence_valid": v["evidence_valid"] if v else None,
                "evidence_errors": v["evidence_errors"] if v else None,
                "wall_seconds": run["wall_seconds"],
                "runtime_seconds": {
                    k: (
                        round(response[k] / 1e9, 4)
                        if response.get(k) is not None
                        else None
                    )
                    for k in [
                        "load_duration",
                        "prompt_eval_duration",
                        "eval_duration",
                        "total_duration",
                    ]
                },
                "prompt_tokens": response.get("prompt_eval_count"),
                "output_tokens": response.get("eval_count"),
                "cold_observed": not any(
                    m.get("name") == report["model"]
                    for m in run["loaded_before"].get("models", [])
                ),
                "review_flags": v["review_flags"] if v else None,
            }
            if run["candidate"] == "A" and v:
                roles = expected[run["case_id"]]["roles"]
                actual = v["output"]
                row["role_differences"] = {
                    uid: {"expected": role, "actual": actual[uid]}
                    for uid, role in roles.items()
                    if role != actual[uid]
                }
                row["relevant_units_correctly_organized"] = [
                    uid
                    for uid, r in roles.items()
                    if r != "other" and actual[uid] == r and r != "mixed_or_unclear"
                ]
                row["relevant_units_in_other"] = [
                    uid
                    for uid, r in roles.items()
                    if r != "other" and actual[uid] == "other"
                ]
                row["relevant_units_requiring_mixed_review"] = [
                    uid
                    for uid, r in roles.items()
                    if r != "other" and actual[uid] == "mixed_or_unclear"
                ]
                row["other_units_misclassified"] = [
                    uid
                    for uid, r in roles.items()
                    if r == "other" and actual[uid] != "other"
                ]
            if run["candidate"] == "B" and v:
                row["proposed_medication_entries"] = len(v["output"]["medications"])
                row["proposed_allergy_statements"] = len(v["output"]["allergies"])
                row["allergy_exact_expected_statements"] = [
                    s["statement"]
                    for s in v["output"]["allergies"]
                    if s["statement"] in expected[run["case_id"]]["allergies"].values()
                ]
                row["allergy_expected_not_intact"] = [
                    s
                    for s in expected[run["case_id"]]["allergies"].values()
                    if s not in [x["statement"] for x in v["output"]["allergies"]]
                ]
            rows.append(row)
    repeat = []
    for candidate in ["A", "B"]:
        rs = [
            r
            for r in reports[0]["runs"]
            if r["candidate"] == candidate and r["case_id"] == "DEV-002"
        ]
        repeat.append(
            {
                "candidate": candidate,
                "case_id": "DEV-002",
                "prompt_revision": 1,
                "exact_content_equal": rs[0]["response"]["message"]["content"]
                == rs[1]["response"]["message"]["content"],
                "first_wall_seconds": rs[0]["wall_seconds"],
                "repeat_wall_seconds": rs[1]["wall_seconds"],
                "limitation": "One repeat only, not general determinism.",
            }
        )
    summary = {
        "status": "Mechanical diagnostics against frozen unreviewed expectations; not clinical accuracy or cross-representation accuracy comparison",
        "runs": rows,
        "repeatability": repeat,
    }
    (DATA / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    esc = html.escape

    def pre(value):
        return (
            "<pre>"
            + esc(
                value
                if isinstance(value, str)
                else json.dumps(value, ensure_ascii=False, indent=2)
            )
            + "</pre>"
        )

    def checklist(e):
        text = "<h4>Medication facts</h4>"
        for med in e["medications"]:
            text += (
                "<p>" + esc(" • ".join(f"{k}: {v}" for k, v in med.items())) + "</p>"
            )
        if not e["medications"]:
            text += "<p>No named medication entries expected.</p>"
        for key in ["allergies", "context"]:
            text += (
                "<h4>"
                + key
                + "</h4>"
                + "".join(
                    "<p>" + esc(uid + ": " + value) + "</p>"
                    for uid, value in e[key].items()
                )
            )
        return (
            text
            + "<h4>Absent / must not infer</h4><ul>"
            + "".join("<li>" + esc(x) + "</li>" for x in e["absent"])
            + "</ul><details><summary>Provisional unit-role reference</summary>"
            + pre(e["roles"])
            + "</details>"
        )

    def proposal(r):
        v = r["validation"]
        if not v:
            return "<p>Invalid/incomplete output. No partial acceptance.</p>"
        if r["candidate"] == "A":
            text = ""
            for role, units in v["groups"].items():
                if not units:
                    continue
                body = "".join(
                    "<p>" + esc(u["source_unit"] + ": " + u["text"]) + "</p>"
                    for u in units
                )
                label = role + f" ({len(units)} units)"
                text += (
                    (
                        "<details><summary>"
                        + esc(label)
                        + (
                            " — REVIEW REQUIRED; not discarded"
                            if role == "mixed_or_unclear"
                            else ""
                        )
                        + "</summary>"
                        + body
                        + "</details>"
                    )
                    if role in ["other", "mixed_or_unclear"]
                    else "<h4>" + esc(label) + "</h4>" + body
                )
            return text
        data = v["output"]
        text = '<p class="notice">Proposals only. Evidence errors and association checks require correction/review; no row is automatically accepted.</p>'
        for kind in ["medications", "allergies", "medication_context"]:
            text += "<h4>" + kind + "</h4>"
            if not data[kind]:
                text += "<p>[]</p>"
            for item in data[kind]:
                text += '<div class="proposal">' + "".join(
                    "<p><b>"
                    + esc(k)
                    + ": </b>"
                    + esc("null" if value is None else str(value))
                    + "</p>"
                    for k, value in item.items()
                    if k != "evidence"
                )
                text += (
                    "<details><summary>Linked evidence: "
                    + esc(", ".join(e["source_unit"] for e in item["evidence"]))
                    + "</summary>"
                    + pre(item["evidence"])
                    + "</details></div>"
                )
        return text

    parts = [
        """<!doctype html><html lang="en"><meta charset="utf-8"><title>Medication representation review — fictional, unreviewed</title><style>body{font:15px/1.5 system-ui,sans-serif;color:#172727;margin:32px;max-width:1600px}h1{font-size:26px}.notice{padding:12px;background:#fff2d8;border-left:4px solid #96732a}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}section{border:1px solid #bdcaca;padding:16px;min-width:0}pre{font:13px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}p{overflow-wrap:anywhere;margin:5px 0}h2{margin-top:45px}summary{cursor:pointer;font-weight:bold;padding:8px 0}.proposal{border:1px solid #b8c5c5;padding:10px;margin:12px 0}.review{border:1px dashed #777;min-height:70px;padding:12px}@media(max-width:800px){.grid{display:block}}@media print{body{margin:10mm;font-size:10pt}pre{font-size:9pt}.grid{display:block}section{margin-bottom:10px}h2,h3{break-after:avoid} }</style><h1>Medication / allergy representation comparison</h1><p class="notice">Fictional development data only. All labels await clinician review. These are proposals and diagnostic expectations, not approved referrals, training exports or clinical validation. No clinician timing was collected; no time-saved estimate. Both v1 failures and the single v2 revision are retained. Expand details to inspect evidence and mixed items; lexical matches do not certify associations.</p>"""
    ]
    for c in cases:
        cid = c["case_id"]
        parts.append(
            "<h2>"
            + esc(cid)
            + "</h2><p>"
            + esc(c["label_kind"])
            + " · "
            + esc(c["underlying_case_id"])
            + '</p><div class="grid"><section><h3>Unchanged original note</h3>'
            + pre(c["source_note"])
            + "</section><section><h3>Frozen expected facts — NOT model input</h3>"
            + checklist(expected[cid])
            + "</section></div>"
        )
        for rev, report in enumerate(reports, 1):
            if rev == 1:
                parts.append(
                    "<details><summary>Preserved first-run proposals — revision 1</summary>"
                )
            parts.append(f'<h3>Prompt revision {rev}</h3><div class="grid">')
            for candidate in ["A", "B"]:
                r = next(
                    r
                    for r in report["runs"]
                    if r["candidate"] == candidate
                    and r["case_id"] == cid
                    and not r["repeat"]
                )
                raw = (
                    r.get("response", {})
                    .get("message", {})
                    .get("content", r.get("raw_response", "No complete response"))
                )
                parts.append(
                    "<section><h3>"
                    + candidate
                    + (
                        " — per-unit roles"
                        if candidate == "A"
                        else " — proposed values and evidence"
                    )
                    + "</h3><p>"
                    + esc(
                        f"{r['wall_seconds']} seconds; structural error: {r['error']}; lexical evidence valid: {r['validation']['evidence_valid'] if r['validation'] else 'unavailable'}"
                    )
                    + "</p>"
                    + proposal(r)
                )
                parts.append(
                    "<details><summary>Complete raw JSON, original units / offsets and validation flags</summary>"
                    + pre(raw)
                    + pre(
                        {
                            "source_mapping": r["source_mapping"],
                            "evidence_errors": (
                                r["validation"]["evidence_errors"]
                                if r["validation"]
                                else None
                            ),
                            "review_flags": (
                                r["validation"]["review_flags"]
                                if r["validation"]
                                else None
                            ),
                        }
                    )
                    + "</details></section>"
                )
            parts.append("</div>")
            if rev == 1:
                parts.append("</details>")
        parts.append(
            '<div class="review"><strong>Clinician adjudication — unfilled:</strong> recovered / omitted facts; wrong roles or associations; allergy wording; unsupported proposals; mixed items; corrections required. Reviewer/date: __________. This sheet does not update review status.</div>'
        )
    parts.append("</html>")
    (DATA / "clinician-review.html").write_text("\n".join(parts))
    print(
        "Saved summary and clinician-review.html; no inference, training or label changes."
    )


if __name__ == "__main__":
    main()
