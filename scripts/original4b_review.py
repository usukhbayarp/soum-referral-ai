"""Compare saved fictional outputs; never calls inference or changes reference labels."""

import html
import json
from collections import Counter
from pathlib import Path
from scripts.medication_experiment import load_cases, DATA
from scripts.original4b_comparison import OUT

ROLE = {
    "regular_medication": "Тогтмол эм",
    "administered_treatment": "Энэ үзлэгээр өгсөн",
    "historical_medication": "Өмнөх эмчилгээ",
    "planned_or_prescribed_treatment": "Төлөвлөсөн",
    "explicitly_not_administered": "Өгөөгүй",
    "mixed_or_unclear": "Холимог / тодорхойгүй",
    "allergy_statement": "Харшил",
    "other": "Бусад",
}
# Keep exact role keys available; use frozen definitions for unknown spelling.
LABEL = {
    "name": "Нэр",
    "role": "Үүрэг",
    "dose": "Тун",
    "route": "Зам",
    "time": "Цаг",
    "frequency": "Давтамж",
    "statement": "Тэмдэглэл",
}
esc = html.escape


def p(text):
    return "<p>" + esc(str(text)) + "</p>"


def proposal(r):
    v = r.get("validation")
    if not v:
        return p("Бүтэц буруу / бүрэн бус хариу: " + str(r.get("error")))
    s = p(
        f"{r['wall_seconds']:.2f} секунд • бүтцийн шалгалт зөв • эхийн хатуу шалгалт: {v['evidence_valid']}"
    )
    if r["candidate"] == "A":
        for role, units in v["groups"].items():
            if not units:
                continue
            body = (
                "<h4>"
                + esc(ROLE.get(role, role))
                + "</h4>"
                + "".join(p(u["text"]) for u in units)
            )
            s += (
                (
                    "<details><summary>Бусад — орхигдсон баримт байгаа эсэхийг шалгана</summary>"
                    + body
                    + "</details>"
                )
                if role == "other"
                else body
            )
    else:
        for kind, title in [
            ("medications", "Эмийн санал"),
            ("allergies", "Харшил"),
            ("medication_context", "Нэмэлт нөхцөл"),
        ]:
            s += "<h4>" + title + "</h4>"
            for item in v["output"][kind]:
                s += '<div class="entry">' + "".join(
                    p(
                        LABEL.get(k, k)
                        + ": "
                        + (
                            ROLE.get(x, x)
                            if k == "role"
                            else str(x) if x is not None else "Бичээгүй / саналгүй"
                        )
                    )
                    for k, x in item.items()
                    if k != "evidence"
                )
                s += (
                    "<details><summary>Холбосон эх</summary>"
                    + "".join(p(e["quote"]) for e in item["evidence"])
                    + "</details></div>"
                )
            if not v["output"][kind]:
                s += p("Санал байхгүй — эхийг өөрөө шалгана.")
    s += (
        "<details><summary>Техникийн шалгалтын алдаа (эмнэлзүйн үнэлгээ биш)</summary><pre>"
        + esc(json.dumps(v["evidence_errors"], ensure_ascii=False, indent=2))
        + "</pre></details>"
    )
    return s


def main():
    cases = load_cases()
    expected = json.loads((DATA / "expected-facts.json").read_text())["cases"]
    rows = []
    reports = {}
    for label, base in [("1.7B", DATA), ("original 4B", OUT)]:
        for rev in (1, 2):
            report = json.loads((base / f"run-v{rev}/report.json").read_text())
            reports[label, rev] = report
            for r in report["runs"]:
                v = r.get("validation")
                response = r.get("response", {})
                row = {
                    "model": label,
                    "identity": report["model"],
                    "digest": report["pinned_digest"],
                    "revision": rev,
                    "case_id": r["case_id"],
                    "candidate": r["candidate"],
                    "repeat": r["repeat"],
                    "abstention": bool(v)
                    and (
                        all(x == "other" for x in v["output"].values())
                        if r["candidate"] == "A"
                        else not any(v["output"].values())
                    ),
                    "structural_valid": bool(v),
                    "evidence_valid": v["evidence_valid"] if v else None,
                    "error": r.get("error"),
                    "wall_seconds": r["wall_seconds"],
                    "cold": not any(
                        m["name"] == report["model"]
                        for m in r["loaded_before"].get("models", [])
                    ),
                    "termination": response.get("done_reason"),
                    "timings_seconds": {
                        k: response.get(k, 0) / 1e9
                        for k in [
                            "load_duration",
                            "prompt_eval_duration",
                            "eval_duration",
                        ]
                    },
                    "evidence_error_counts": (
                        dict(Counter(e["type"] for e in v["evidence_errors"]))
                        if v
                        else {}
                    ),
                }
                if v and r["candidate"] == "A":
                    actual = v["output"]
                    want = expected[r["case_id"]]["roles"]
                    row["role_differences"] = {
                        k: {"expected": x, "actual": actual[k]}
                        for k, x in want.items()
                        if actual[k] != x
                    }
                    row["missing_and_extra_by_role"] = {
                        role: {
                            "missing": [
                                k
                                for k, x in want.items()
                                if x == role and actual[k] != role
                            ],
                            "extra": [
                                k
                                for k, x in actual.items()
                                if x == role and want[k] != role
                            ],
                        }
                        for role in sorted(set(want.values()) | set(actual.values()))
                    }
                rows.append(row)
    summary = {
        "status": "Frozen unreviewed development expectations; mechanical diagnostics, not clinical accuracy",
        "runs": rows,
        "repeats": [],
    }
    for label in ["1.7B", "original 4B"]:
        for candidate in ["A", "B"]:
            r = [
                r
                for r in reports[label, 1]["runs"]
                if r["candidate"] == candidate and r["case_id"] == "DEV-002"
            ]
            summary["repeats"].append(
                {
                    "model": label,
                    "candidate": candidate,
                    "identical_content": (
                        r[0]["response"]["message"]["content"] == r[1]["response"]["message"]["content"]
                        if all(x.get("response", {}).get("message", {}).get("content") is not None for x in r)
                        else None
                    ),
                    "errors": [x.get("error") for x in r],
                }
            )
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    s = """<!doctype html><html lang="mn"><meta charset="utf-8"><title>v0.7 — Эмийн саналын эмчийн хяналт</title><style>body{font:16px/1.5 Arial;margin:24px;color:#17263c}h2{border-bottom:2px solid #6b7d90}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.cell,.entry{border:1px solid #ccd5df;padding:12px;margin:8px 0;min-width:0}pre{white-space:pre-wrap;overflow-wrap:anywhere}p{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}textarea{width:98%;min-height:85px}section{margin-bottom:36px}@media(max-width:800px){.grid{display:block}}</style><h1>Эмийн ялгалтын санал — эмчийн хяналт</h1><p>Бүх 4 тохиолдол зохиомол, хөгжүүлэлтийн, эмч хянаагүй. Зөв хариуны төсөөлөл ч эмчийн баталгаа биш. Энэ хуудсанд бичсэн зүйл хадгалагдахгүй: хуулж тусад нь хадгална. Token ID / JSON засах шаардлагагүй.</p>"""
    annotations = []
    for case in cases:
        cid = case["case_id"]
        e = expected[cid]
        s += (
            "<section><h2>"
            + esc(cid)
            + '</h2><div class="grid"><div class="cell"><h3>Өөрчлөгдөөгүй эх</h3><pre>'
            + esc(case["source_note"])
            + '</pre></div><div class="cell"><h3>Хянагдаагүй хүлээгдэж буй баримт</h3>'
        )
        for med in e["medications"]:
            s += p(
                " • ".join(
                    LABEL.get(k, k) + ": " + (ROLE.get(v, v) if k == "role" else str(v) if v is not None else "Эхэд бичээгүй / тодорхойгүй")
                    for k, v in med.items()
                    if k != "units"
                )
            )
        for kind in ["allergies", "context"]:
            s += "".join(p(x) for x in e[kind].values())
        s += (
            "<h4>Байхгүй / таамаглаж болохгүй</h4>"
            + "".join(p(x) for x in e["absent"])
            + "</div></div>"
        )
        for rev in (1, 2):
            s += "<h3>Хадгалсан prompt хувилбар " + str(rev) + "</h3>"
            for model in ["original 4B", "1.7B"]:
                body = "<h4>" + esc(model) + '</h4><div class="grid">'
                for candidate in ["A", "B"]:
                    r = next(
                        r
                        for r in reports[model, rev]["runs"]
                        if r["case_id"] == cid
                        and r["candidate"] == candidate
                        and not r["repeat"]
                    )
                    body += (
                        '<div class="cell"><h3>'
                        + candidate
                        + (
                            " — эхийн ангилал"
                            if candidate == "A"
                            else " — бүтэцтэй утга"
                        )
                        + "</h3>"
                        + proposal(r)
                        + "</div>"
                    )
                body += "</div>"
                s += (
                    body
                    if model == "original 4B"
                    else "<details><summary>Өмнөх 1.7B саналууд</summary>"
                    + body
                    + "</details>"
                )
        questions = {
            "DEV-002": "Амлодипин тогтмол уу, парацетамол энэ үзлэгээр өгсөн үү? Өнөөдрийн тунг асуугаагүй, өвчтөн харшилгүй гэж хэлсэн, өөр эмчилгээ хийгээгүй гэдгийг хадгалсан уу? Давтамжийг цаг болгон буруу шилжүүлсэн үү?",
            "dev-003": "Харшилгүй ба эмчилгээ хийгээгүй гэсэн хоёр өөр үгүйсгэлийг хоёуланг нь хадгалсан уу? Хоосон санал нь эдгээрийг орхисон уу? Шинжилгээ хийгдээгүй гэдгийг эмчилгээтэй хольсон уу?",
            "dev-004": "Өвчтөн парацетамол уусан гэдэг нь энэ үзлэгээр эмч өгсөн эсвэл тогтмол эм гэсэн баталгаа мөн үү? Өмнөх амоксициллины давтамж, хугацааг тусад нь хадгалсан уу? Пенициллиний тууралтыг өгөөгүй эмийн мөр болгосон уу?",
            "probe-med-001": "Нэг өгүүлбэр дэх тогтмол амлодипин ба өгсөн парацетамолын мэдээллийг салгасан уу? 10:15 цаг аль эмийнх вэ? Ибупрофен төлөвлөсөн, диклофенак өгөөгүй, нэргүй эм уусан ба харшлыг асуугаагүй/тодорхойгүйг ялгасан уу?",
        }
        s += p(questions[cid])
        s += (
            "<h3>Эмч шийдэх зүйл</h3>"
            + p(
                "Тогтмол / энэ үзлэгээр өгсөн / өмнөх / төлөвлөсөн / өгөөгүйг зөв ялгасан уу? Тун, зам, цаг, давтамж зөв эмтэй холбогдсон уу? Харшлын үгүйсгэл, асуугаагүй байдал, өвчтөний хэлсэн гэдэг нь хадгалагдсан уу? Аль баримт орхигдсон, ямар гар засвар үлдэв? Үг үсгийн зөрүү ба буруу холбоосыг тусад нь тэмдэглэнэ."
            )
            + '<label>Эмчийн засвар ба шалтгаан<textarea placeholder="Хянагдаагүй — эмч бөглөнө"></textarea></label><p>Хянасан эмч: __________ Огноо: __________ Хяналтын төлөв: ХЯНАГДААГҮЙ</p></section>'
        )
        annotations.append(
            {
                "case_id": cid,
                "underlying_case_id": case["underlying_case_id"],
                "source_note": case["source_note"],
                "split": "development",
                "synthetic_origin": case["synthetic_origin"],
                "clinician_review_status": "unreviewed",
                "reviewer": None,
                "reviewed_at": None,
                "form_version": "experimental-0.7",
                "extraction_contract": "medication-representation-1",
                "prompt_versions": [
                    "medication-A-1",
                    "medication-B-1",
                    "medication-A-2",
                    "medication-B-2",
                ],
                "annotation_version": "medication-review-1",
                "source_segmentation_version": "sentence-lines-1",
                "provisional_expected_roles": e["roles"],
                "provisional_expected_facts": e["medications"],
                "provisional_allergies": e["allergies"],
                "provisional_context": e["context"],
                "missing_absent_not_assessed_to_adjudicate": e["absent"],
                "evidence_mapping_reference": "../medication-v1/expected-facts.json",
                "review_notes": None,
                "training_eligible": False,
            }
        )
    s += "</html>"
    (OUT / "clinician-review.html").write_text(s)
    (OUT / "annotation-drafts.json").write_text(
        json.dumps(annotations, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        "Saved comparison summary, human review sheet and unreviewed annotation drafts."
    )


if __name__ == "__main__":
    main()
