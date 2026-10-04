"""Fictional normal/stress print mechanics. Requires an existing pypdf environment."""

import hashlib
import json
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
reports = []
for name, relative in [
    ("normal_before", ".runtime/recovery-print/normal-before.pdf"),
    ("normal_after", ".runtime/recovery-print/normal-after.pdf"),
    ("stress_after", ".runtime/recovery-stress/v06-multipage.pdf"),
]:
    path = ROOT / relative
    pages = [p.extract_text() for p in PdfReader(path).pages]
    assert all("DEV-002" in p for p in pages)
    text = "\n".join(pages)
    if name == "normal_after":
        for value in [
            "134/82",
            "128/80",
            "36.7",
            "36.6",
            "500 мг",
            "6/10",
            "4/10",
            "асуугаагүй",
            "үнэлээгүй",
            "RF",
            "anti-CCP",
            "CRP",
            "хийгээгүй",
            "Гарын үсэг",
            "Бөглөөгүй",
        ]:
            assert value in text, value
        assert "Эхийн санал төдий" not in text
        assert "энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй" in text
    if name == "stress_after":
        assert len(pages) > 1 and "Мөр 35:" in text and "Ө ө Ү ү" in text
        for n in (1, 2, 3):
            assert (
                sum(
                    f"ХЭВЛЭЛТИЙН-ТУРШИЛТ-{n}" in p and f"Туршилтын мөр {n} төгсгөл" in p
                    for p in pages
                )
                == 1
            )
    reports.append(
        {
            "fixture": name,
            "pages": len(pages),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "status": "pass",
            "pdf": relative,
        }
    )
report = {
    "status": "fictional print mechanics only; browser acknowledgement simulated, clinician signature/review unfilled",
    "checks": [
        "ID on every page",
        "normal source facts/negatives/units and time-only values retained",
        "manual attribution without original-evidence duplication",
        "three stress treatment rows individually unbroken",
        "long-text final line retained",
    ],
    "visual_inspection": "required separately; text checks do not prove layout quality",
    "results": reports,
}
(ROOT / "evaluation/recovery-v06/print-check.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(report, ensure_ascii=False, indent=2))
