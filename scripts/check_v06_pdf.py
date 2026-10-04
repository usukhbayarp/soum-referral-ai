"""Check the fictional browser stress PDF; use an existing pypdf environment.
Visual inspection is still required. This never evaluates clinical correctness.
"""

import hashlib
import json
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / ".runtime/v06-ui/v06-multipage.pdf"
reader = PdfReader(path)
pages = [p.extract_text() for p in reader.pages]
assert len(pages) > 1
assert all("DEV-002" in page for page in pages)
assert "Мөр 35:" in "".join(pages)
assert "Ө ө Ү ү" in "".join(pages)
for n in (1, 2, 3):
    assert (
        sum(
            f"ХЭВЛЭЛТИЙН-ТУРШИЛТ-{n}" in page and f"Туршилтын мөр {n} төгсгөл" in page
            for page in pages
        )
        == 1
    )
report = dict(
    status="pass",
    pdf_pages=len(pages),
    pdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    checks=[
        "identifier every page",
        "all three treatment rows each fit on one page",
        "long-text final line present",
        "Mongolian Ө ө Ү ү extractable",
    ],
    visual_inspection="required separately; text extraction alone does not prove unclipped readable rendering",
    fixture="fictional browser stress test using provisional labels; not clinical/model/offline validation",
)
(ROOT / "evaluation/dev002-v06/print-check.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(report, ensure_ascii=False, indent=2))
