# Milestone verification — 2026-10-04

## Deterministic automated checks (mock inference)

32 Python tests passed; eight Node state-machine tests passed. `pip check` found no broken requirements. One dependency deprecation warning from Starlette/AnyIO remains; no test failures.

Covered:
- Unknown, negative, duplicate, boolean, string and floating evidence IDs; malformed, missing and duplicate JSON keys; unexpected structure.
- Exact source slicing, Unicode offsets, explicit negatives/unknown statements, numbers/units/temporal ordering and multiple field assignments.
- Input character/unit/byte limits; non-JSON and cross-origin rejection; response no-store/CSP headers; no note content echoed in validation errors.
- Failure distinct from empty assignments; incomplete model output, unexpected thinking, output limits and malformed runtime envelope.
- Inference timeout using a delayed mock transport; one active request plus bounded waiting queue, overload, queue timeout and cancellation release.
- Two concurrent synthetic requests cannot mix field/source content.
- Edits revoke approval; source changes, edits and reset invalidate outstanding tickets; original evidence survives doctor edits; reset clears content.
- Dataset leakage across underlying cases/splits, invalid labels and versions; exports include only reviewed train/development; all unreviewed development fixtures are rejected for training export.

These tests do not establish real model correctness or runtime timeout cancellation behavior inside Ollama.

## Real local inference

Ollama 0.34.0 was reused on loopback. `qwen3:1.7b` was downloaded and digest-verified by Ollama. Cached text-only `qwen3:4b` loaded successfully and metadata revealed its Thinking-2507 variant. Twenty comparison calls (five cases × two models × two prompt versions) completed; all produced structurally valid ID output. Bad categorization and omissions were observed and recorded in `evaluation/report.md`; no clinical scores exist.

A real Chrome UI → FastAPI → Ollama → source evidence flow was exercised. A doctor edit made during real inference was retained and the late reply visibly discarded. No mocked response was used for that browser race check.

## Browser/print checks on macOS Chrome

- Fictional source and manual fields accept Mongolian Cyrillic.
- Injected test string `<img src=x onerror=alert(1)>` appeared as literal text in source and print content; zero inserted image elements were present. No alert occurred.
- Manual completion works without a successful extraction.
- Approval with eight unresolved fields succeeded only after both review and unresolved-item acknowledgments. The print content explicitly labeled unresolved items.
- Browser print preview rendered a complete one-page A4 sample with readable Mongolian Cyrillic, negative statement “Халуураагүй.”, prototype/fictional-data label and export-handling footer. No file was saved for the injected-string test.
- Editing a field after approval disabled print, removed approved state and cleared generated print content.
- Reset cleared all textareas, source/evidence display and generated print content.
- The real-inference example and evidence highlight were inspected separately; original extracted text remains accessible after doctor edits.

## Local assets and privacy checks

Application UI uses only local HTML/CSS/JS/SVG and system fonts. Source inspection found no CDN/remote asset links, HTML insertion sinks, browser persistent storage or analytics. Application access logging is disabled in documented/current startup. No interactive patient state is stored server-side; HTTP bodies/model responses are never explicitly logged. Existing cache contents were preserved.

Public staging review excludes environments, credentials, weights, private notes, unrelated project content and local runtime artifacts. Public evaluation artifacts contain only the five explicitly fictional, unreviewed development fixtures and their outputs.

## Pending (not claimed)

- True network-disconnected restart/cold-load/extract/edit/print test. The computer was not disconnected.
- Windows/Linux execution, performance and Cyrillic/font/print behavior; representative low-spec devices.
- Long multi-page print stress testing and maximum accepted note/output runtime behavior.
- Clinician validation, held-out quality evaluation, adversarial prompt robustness, general contradiction detection (not implemented).
- Hosted multi-user deployment, shared/distributed queue, authentication/access control, HTTPS and operational retention review.
- MLX model loading, training, merging, GGUF conversion or Ollama import of a tuned model.
