# Reviewed-data preparation and bounded medfacts baseline — 2026-10-04

This is engineering preparation and partial reviewed-development diagnostics, **not clinical validation**. No quality optimizer steps, new model import, production model/prompt change, live-app restart, hosting, submission, download or network-disconnection test occurred. Existing artifacts, tags and contracts remain intact. Starting main was `d4b384a42256caab0508ae8611b1487e8b0298b6`.

## Authoritative training material

`training/reviewed-medfacts-v1/cases.json` and the two `.txt` files preserve the exact supplied notes, original S IDs, SHA-256 hashes, listed answer text and hashes, reviewer **А. Балжинням**, date **2026-10-04**, fictional origin and train-only independent family IDs. Review scope is the supplied source and explicitly listed answers, not every possible fact in the note. `mapped-cases.json` adds faithful engineering mappings with deterministic `sentence-lines-1` U IDs, original codepoint offsets and S links. The manifest pins both mappings and the successor contract.

TRAIN-002 revision `approved-revised-20261004-2` records final approval superseding draft status. S03 is exactly **Одоо өөр эм тогтмол хэрэглэдэг эсэх нь тодорхойгүй.** The earlier full draft was unavailable in the repository; its absence and the supplied change history are recorded without reconstructing it. TRAIN-001's not-asked statements remain unchanged. There is no global wording replacement.

TRAIN-001 has 11 scoped facts; TRAIN-002 has 10. Unlisted examination/history details are not invented targets. In particular, TRAIN-002's anemia history is not given an additional chronic-history target. All four previously used development families stay development, including unreviewed probe-med-001, which is excluded from this baseline. No final-test contents were opened; a real final-test family registry is still needed before final evaluation.

## Frozen successor contract

**`source-linked-medfacts-1` / prompt `medfacts-1`** is frozen for this experiment in `experiments/medfacts-v1`. It has topics, independent positive attributes, exact evidence and optional context links. It is not integrated into production and does not reinterpret old A/B results.

Representative approved TRAIN-001 target:

```json
{"topic":"medication","attributes":["regular_use","patient_reported"],"evidence":[{"unit_id":"U3","quote":"левотироксин 50 мкг өглөө өлөн үед өдөр бүр уудаг гэсэн."}],"context":["U4"]}
```

Regular use and home/pre-encounter use can coexist when both are documented. They are independent of encounter administration. Historical/stopped, planned/not-yet-given, unknown, not asked, not documented, not clarified and explicit absence remain distinguishable. Separate facts can share one S paragraph or unit. Context links do not approve every fact in that context. Full original notes remain available; only presentation S prefixes are removed from the model-facing U view using the established mapping. No original source bytes are changed.

Medication details remain exact quoted text rather than a generated dose/route/time table. This preserves мкг versus мг, patient attribution, no-other-medication versus no-other-treatment, and the famotidine documentation time. No infusion rate, causal response or anaphylaxis is inferred. Planned CBC without a specimen is not a pending result. Oral normalization remains an optional linked display rule, not a generated training field.

**Limits:** implicit absence of a detail (e.g. famotidine frequency) has no invented source quote or standalone label; the approved answer text is retained for manual detail checks. The compact contract does not independently score every drug–dose/time association. Exact lexical evidence is necessary but never establishes semantic correctness. No clinician question blocks the faithful mappings already approved. The older dev-004 clarification draft remains unapproved and unused; no new approval is requested for the two approved training cases.

## Development scope and observed baseline

Only nine supported facts are mapped: DEV-002 five, dev-003 three, dev-004 one investigation. Other approved categories outside this compact task and unreviewed facts are not filled with `other`, `unknown` or negative labels. These are **explicitly scoped tasks with the full note as context**, not complete-referral extraction tests. Partial labels are never exported as whole-note `valid.jsonl`; whole-target development loss is unavailable.

One attempt for each of three development inputs used the conversion-matched untuned control:

- Tag `soum-qwen3-4b-control:mlx128-52a5ab34`; digest `a7949c7fd19f24caf6f062c16c5733fa72c5c8049a53ec34681ccc426b6eb5f6`.
- Source/tokenizer `Qwen/Qwen3-4B-MLX-4bit@52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495`; affine 4-bit/group 128, converted BF16 HF → F16 GGUF → Q4_K_M.
- Preserved template SHA `ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4`; think=false, temperature 0, seed 42, context 16384, output bound 3200 tokens, timeout 120 seconds, no retries or sweep.

| Input | Contract-valid | Correct / incorrect / unscorable reviewed facts | Prompt/output tokens | Total request wall time |
|---|---|---|---|---|
| DEV-002 | Yes, incomplete | 1 / 4 / 0 | 2727 / 64 | 14.85 s |
| dev-003 | No | 0 / 0 / 3 | 1476 / 146 | 8.17 s |
| dev-004 | No | 0 / 0 / 1 | 1535 / 44 | 3.91 s |

Total **26.93 seconds**, including all three calls and loads. Zero timeout/empty responses. All three were parseable JSON, but two failed contract/evidence checks; JSON validity is not success. Requests, serialized wire bodies, responses, token counts, exact spans, errors and reviewed denominators are preserved in `evaluation/medfacts-v1/untuned-baseline.json`.

DEV-002 retained regular amlodipine but omitted not-asked current dose, patient-reported allergy absence, administered paracetamol and no-other-treatment. dev-003 collapsed three distinct negative statements into medication evidence and emitted incompatible use/uncertainty attributes. dev-004 copied the prompt's placeholder quote instead of source text. These remain failures, not repaired predictions. Exact-span mismatches and alternate overlapping selections are reported for review; unreviewed extra attributes/facts are not automatically counted as clinical errors. No candidate is demonstrated usable. The future diagnostic pilot must still require manual review; do not switch defaults.

## Observed sequence length and capacity

Existing environment reused: MLX **0.30.6**, MLX-LM **0.30.7**, transformers **5.2.0**, huggingface-hub **1.4.1**, Python **3.13.5** via `/opt/anaconda3/bin/python -m scripts.mlx_python`. Base files and installed versions were checked against existing pins. No second stack installed.

| Case | Prompt | Completion including EOS | Full sequence |
|---|---:|---:|---:|
| TRAIN-001 | 1982 | 708 | 2690 |
| TRAIN-002 | 2017 | 710 | **2727** |

Actual pinned tokenizer and installed MLX-LM ChatDataset verified the exact non-thinking serving prefix, completion-only mask and EOS; no truncation. One supervised batch-one forward/backward probe at **2727** tokens passed with finite loss/gradients and unchanged adapter parameters. **Zero optimizer steps**, no persistent weight update. The observed loss 0.3574 is a capacity diagnostic, not a quality result.

MLX peak **5,666,172,944 bytes (5.28 GiB)**; model interval **16.60 s**, supervised process **28.34 s**. Sampled child RSS peaked at **1,919,968 KiB**, system free-memory metric reached **29%**, pressure levels 1 and 2 occurred, never critical 4. These overlapping memory metrics must not be added. Hardware is the existing 16-GiB M4; approximately **36.8 GiB** disk free at handoff measurement. Batch one, rank two on last-block q/v, gradient checkpointing, 8-GiB MLX limit, 128-MiB cache and existing watchdog remain unchanged. A four-step optimizer run and its optimizer-state memory are **not yet tested**; watchdog limits remain necessary.

## History destination fix and verification

Form v0.8 revision `history-destination-2` maps legacy `medical_history` proposals into a separate **Өмнөх түүх — ангилаагүй эхийн санал** review field. Current-illness history and chronic history remain manual; neither is automatically filled or inferred from medication names. Re-extraction preserves manual entries. Source edits require reconciliation and revoke approval/print content. Source suggestions are omitted from print; both history fields remain full-width with honest manual attribution.

**116 Python tests and 32 JavaScript tests passed** (one existing Starlette/AnyIO deprecation warning). Reviewed export/capacity preflight and exact source-note preservation checks passed. The prepared pilot/export scripts passed syntax and focused unit checks; the future training/export run remains unexecuted.

An isolated app at port 8001 and a mocked-extraction browser check verified destination separation, preserved manual histories, approval/print attribution, source reconciliation and example reset. The owned process was stopped afterward. **The existing live port-8000 process still reports `experimental-0.7`**; no restart occurred. Production remains `qwen3:1.7b` / `source-id-v06-1`. Old v0.8 milestone reports describe historical behavior and remain unchanged.

## Prepared quality pilot — not executed

The reviewed scoped export is already at `.runtime/quality-medfacts-v1/train.jsonl`, with two records and a provenance manifest. To regenerate on another checkout, use a fresh ignored output directory with `python -m scripts.medfacts_data --output ...`. The pilot rejects changed sources/mappings/contract, fabricated valid/test files, incomplete baseline or missing actual-length capacity success. Tokenization again refuses truncation.

Prerequisites for a later authorized run: unchanged reviewed export and pins; idle/unloaded Ollama (wait for its own expiry, do not interrupt a doctor's inference); existing base/tokenizer and environment; fresh output/log paths; conservative memory/watchdog limits and adequate free disk. New or longer examples require a new approved mapping revision and capacity check. The two families support only a diagnostic pilot. A real held-out family registry and broader independent reviewed data are prerequisites for any general quality/clinical claim, not invented in this milestone.

From the repository root, the **ready-to-run command after separate authorization** is:

```sh
.venv/bin/python -m scripts.watched_job --report .runtime/quality-medfacts-v1-watch.json /opt/anaconda3/bin/python -m scripts.mlx_python scripts.medfacts_pilot .runtime/quality-medfacts-v1 --output .runtime/quality-medfacts-v1-pilot --run-quality-pilot
```

It is fixed at batch one, rank two, last-block q/v, Adam learning rate 1e-5, seed 42, two passes over two cases: **four steps maximum**, checkpoints **2 and 4**. Step zero remains the conversion-matched untuned baseline. There is no scheduler/sweep, fabricated dev loss, automatic model promotion or application reconfiguration. Nonfinite loss/gradients stop before updating. Training loss, source/export provenance, adapter hashes and measured memory are recorded, never treated as evidence of clinical improvement.

### Future export and selection

`export_reviewed_adapter.py` reuses the successful low-memory route, enumerates **all** LoRA A/B pairs, rejects unsupported/unpaired parameters and verifies each adapted base tensor against the existing control HF. It verifies fused values, all output tensor shapes/dtypes/index, replacement hashes and every untouched tensor. There is no hard-coded two-tensor assumption. A conservative **256-MiB dense patch budget** rejects larger adaptations explicitly instead of skipping tensors. Pair enumeration beyond two modules is unit-tested; this generalized future exporter has **not performed a new weight export** here. The historical two-tensor successful export remains preserved.

For each checkpoint sequentially, choose fresh paths. Example step 2, **not run**:

```sh
ADAPTER=.runtime/quality-medfacts-v1-pilot/step-2
ADAPTER_SHA=$(.venv/bin/python -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path(".runtime/quality-medfacts-v1-pilot/step-2/adapters.safetensors").read_bytes()).hexdigest())')
WORK=.runtime/quality-medfacts-v1-step2
REPORTS=.runtime/quality-medfacts-v1-step2-reports
.venv/bin/python -m scripts.watched_job --report .runtime/quality-step2-fusion-watch.json /opt/anaconda3/bin/python -m scripts.mlx_python scripts.export_reviewed_adapter patches --adapter "$ADAPTER" --adapter-sha256 "$ADAPTER_SHA" --work "$WORK" --reports "$REPORTS"
.venv/bin/python -m scripts.watched_job --report .runtime/quality-step2-hf-watch.json .venv/bin/python -m scripts.export_reviewed_adapter export --adapter "$ADAPTER" --adapter-sha256 "$ADAPTER_SHA" --work "$WORK" --reports "$REPORTS"
```

The full export requires an estimated **21.64 GiB additional free storage** per retained HF/F16/Q4/import path; it checks before copying. Do not delete previous artifacts to force a run. Retaining both checkpoints' large exports may exceed current disk; stop and arrange additional storage or authorized intermediate handling before checkpoint 4. Then verify the unchanged converter checkout is `11fe02151f79c41d0d4af7da708755d73b9c0da6` and use the existing isolated converter/quantizer:

```sh
test "$(git -C .runtime/preparation/llama.cpp rev-parse HEAD)" = 11fe02151f79c41d0d4af7da708755d73b9c0da6
.venv/bin/python -m scripts.watched_job --report .runtime/quality-step2-convert-watch.json .runtime/preparation/converter-env/bin/python -m scripts.mlx_python --script .runtime/preparation/llama.cpp/convert_hf_to_gguf.py "$WORK/candidate-hf" --outfile "$WORK/candidate-F16.gguf" --outtype f16
.venv/bin/python -m scripts.watched_job --report .runtime/quality-step2-quantize-watch.json .runtime/preparation/llama.cpp/build/bin/llama-quantize "$WORK/candidate-F16.gguf" "$WORK/candidate-Q4_K_M.gguf" Q4_K_M
.venv/bin/python -m scripts.import_candidate --gguf "$WORK/candidate-Q4_K_M.gguf" --tag soum-qwen3-4b-medfacts:pilot1-step2 --output "$REPORTS/import"
.venv/bin/python -m scripts.medfacts_baseline --model soum-qwen3-4b-medfacts:pilot1-step2 --output "$REPORTS/development.json"
```

No MLX built-in Qwen GGUF exporter is used. Import refuses an existing tag, preserves the pinned template and verifies existing tags remain unchanged. Run step 4 only after inference expires and storage checks pass, under distinct paths/tag. Compare baseline, step 2, step 4 reports in that order:

```sh
.venv/bin/python -m scripts.medfacts_select evaluation/medfacts-v1/untuned-baseline.json .runtime/quality-medfacts-v1-step2-reports/development.json .runtime/quality-medfacts-v1-step4-reports/development.json --output .runtime/quality-medfacts-v1-selection.json
```

Selection uses the same nine-fact denominator and identical requests/settings/template. Highest reviewed correct count gives only a **diagnostic preference**; ties retain baseline, then earlier checkpoint. Invalid/unscorable outputs and extra facts remain visible. Human review of errors, negation, attribution and unsupported additions is mandatory; no automatic promotion. The smoke tag is rejected as a quality comparison candidate. Production and base/control tags remain available for rollback; these scripts never switch the app.
