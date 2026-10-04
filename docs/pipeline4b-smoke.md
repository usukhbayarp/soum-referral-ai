# Original-4B pipeline verification — bounded engineering milestone

**Observed partial success, not clinical improvement.** Actual three-step adapter training, exact adapter reload, adapter inference and adapter-layer fusion succeeded. The untuned control completed HF → F16 GGUF → Q4_K_M → Ollama import. The smoke-trained full HF export was **stopped at critical memory pressure**, so its GGUF/import/comparison remain blocked. No production app/model/prompt/form changes; no training on the four unreviewed development cases, held-out content access, cloud deployment or network disconnection.

## Source and compatibility

Training checkpoint: [official Qwen/Qwen3-4B-MLX-4bit](https://huggingface.co/Qwen/Qwen3-4B-MLX-4bit/tree/52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495), revision **52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495**. Tokenizer/config come from that same revision. All downloaded files have recorded SHA256; the 2,137,326,367-byte model matches the publisher LFS hash. This is the original dual-mode text-only family, not Thinking-2507 or VL. The exact original full-precision weight revision used to make this official MLX artifact is unpublished; no numerical equivalence with the official GGUF is asserted.

Quantization: 4-bit affine, group size **128**, actual floating tensors **BF16**. Official config differs from the separately inspected HF/GGUF metadata (65536 context, max-window-layers 28, but 36 actual model layers); these differences are recorded, not rewritten. The short smoke exercises 1663 tokens, not maximum context. Publisher card's license link points to a 14B page; the actual repository LICENSE was downloaded and records Apache-2.0. Keep that notice with redistributed artifacts.

Reused versions: MLX **0.30.6**, MLX-LM **0.30.7**, Transformers **5.2.0**, huggingface-hub **1.4.1**. No second stack installed. The existing noninteractive readline workaround is reused. Installed Qwen3 loader, LoRA utilities and [MLX-LM fuse implementation](https://github.com/ml-explore/mlx-lm/blob/v0.30.7/mlx_lm/fuse.py) were inspected and exercised. Converter remains llama.cpp **11fe02151f79c41d0d4af7da708755d73b9c0da6**; observed untuned route is BF16 dequantized HF-compatible weights → llama.cpp F16 GGUF → Q4_K_M → Ollama with the preserved template hash. **Never use MLX's unsupported built-in Qwen GGUF exporter.**

## Stage results

| Stage | Status and evidence |
|---|---|
| Preflight/source pin/download | Observed success; no resident Ollama model or other training process observed before allocation |
| Non-thinking/completion-only mask | Observed success: full 1663 tokens = 1628 prompt + 35 target/EOS; exact expected serving prefix, no truncation |
| Actual optimizer steps | Observed success: batch 1, 3 steps, rank 2, last block q/v only, seed 42, Adam 1e-5 |
| Finite loss | 0.8964285851, 0.8964285851, 0.8928571343; engineering measurement, **not quality improvement** |
| Adapter change | Observed nonzero deltas; final max change about 0.000123825; A tensors begin changing after step 1, B tensors already change at step 1 |
| Saved nonzero adapter reload | Observed success: all saved adapter tensors equal reloaded tensors exactly; 82,361 bytes |
| Adapter inference | Observed execution, 32-token cap; output is incomplete JSON, deliberately **not** an extraction success claim |
| Applying/fusing adapters | Observed success for both trained q/v modules using installed `.fuse(dequantize=True)`; fused weights equal base + scaled low-rank update and differ from base (max BF16 difference 0.000030517578125) |
| Full dequantized HF artifact | Control: observed success, BF16. Smoke: failed safely; pressure level 4 triggered the watchdog at 12.16 s |
| GGUF conversion / Q4_K_M | Control: observed success. Initial direct Python converter exited -11 with no output; existing readline workaround succeeded. Smoke: not attempted |
| Matched untuned control / smoke Ollama imports | Control: observed success, new tag; all previous tags preserved. Smoke: not attempted |
| Three-way serving comparison | Smoke unavailable; only predeclared official/control subset attempted, maximum **8/12 requests**, no retries. See comparison results below |

Separate fictional fixture `training/engineering4b-fixture.json` is AI-created, unreviewed and permanently engineering-only. It never passed through the clinician-reviewed exporter. Its source is rejected by the clinical correction workflow even if someone changes its ID/review status. Initial and final adapter tensors remain local under `.runtime/pipeline4b/smoke`; no weights are committed. No clinical candidate was created or promoted.

The supervised subprocess took **50.63 seconds** including startup/hash checks; measured model-work interval **36.84 seconds**. MLX peak allocated bytes **4,415,189,868 (~4.11 GiB)**; two-second child RSS peak **2,078,608 KiB (~1.98 GiB)**. These overlap; do not add them. System free-memory metric stayed at least 27%; macOS pressure levels 1 and 2 were observed, never critical 4. The watchdog did not intervene. Hard MLX allocation limit 8 GiB, RSS stop 9 GiB, critical-pressure/free-percentage guard, 600-second job bound and Ollama-residency guard applied. Only the owned child could be stopped; the app and shared Ollama service were not restarted.

## Export resources, failures and control

**Observed initial disk block:** 9.5 GiB free before download, about 6.3 GiB after the smoke. Keeping both pipelines' HF/F16 intermediates, Q4 files, conservative Ollama blob copies and a 2-GiB reserve requires an **estimated 41.27 GiB free after the MLX base is present**. The initial guard refused safely: 6.26 GiB available, 35.01 GiB additional needed. No existing caches, models or artifacts were deleted.

A later check found about **40 GiB free**, allowing export to resume. The newly added `scripts.staged_export4b` estimates **26.29 GiB** additional peak with sequential disposal of only its own newly generated, verified intermediates. Its successful control F16 intermediate was removed after hashing and Q4 verification; the earlier failed-run control HF directory remains preserved. The smoke's incomplete directory is also preserved. These temporary-file rules do not authorize deleting any pre-existing artifact. System-wide free-space variation is not attributed to this process.

Control HF export: **25.18 s model/hash interval**, **34.49 s supervised subprocess**, MLX peak **6,288,800,776 bytes (5.86 GiB)**. F16 conversion: **44.47 s**, **8,051,284,800 bytes**. Q4_K_M: **38.43 s**, **2,497,280,320 bytes**. Its SHA256 is `8392d13c0aac3c5d4ff52a888ee85815b1b42835ea9b45468741151dfa306ca0`. These are observed control measurements, not estimates of the failed smoke's maximum allocation.

The first converter command in `staged-export.json` exited **-11**, with empty stdout/stderr. Re-running the same pinned converter through the existing noninteractive `scripts.mlx_python --script` workaround succeeded; no package/converter upgrade was needed. The original failure report remains. The smoke HF command then hit macOS critical pressure **4** at **12.16 s**; the owned child was terminated and the supervisor returned after **12.82 s**. The failed child did not produce a completed HF manifest or MLX peak measurement. Its adapter and prior successful training/fusion evidence remain intact. Pressure returned to **1** and `/api/ps` was empty before proceeding. No smoke export retry or additional training was attempted. The live app/shared Ollama service was never restarted.

Final observed free disk: **22.49 GiB**; macOS pressure **1**. Across sampled export stages, minimum free disk was **20.66 GiB**, and maximum child RSS was **2.63 GiB**. RSS and MLX allocation overlap and do not capture every system/unified-memory allocation; the stopped smoke export has no completed peak-MLX measurement.

Artifacts: `staged-export.json`, `staged-export-recovery.json`, `control-hf.json`, `export-failure.json`, `control-import/import.json`, `imported-pins.json` and `serving-metadata.json` under `evaluation/pipeline4b-smoke`. Historical initial-block reports remain unchanged. A small later runner fix gives logs unique report names and records terminated-child exit status; `export-failure.json` pins the code actually executed before that diagnostic improvement. The legacy all-intermediates `pipeline4b_export.sh` remains a prepared alternative, not an end-to-end tested smoke route; do not rerun over these outputs.

- **Installed:** `soum-qwen3-4b-control:mlx128-52a5ab34`.
- **Not installed:** `soum-qwen3-4b-pipeline-test:step3-52a5ab34` (full export blocked).
- **Preserved reference:** `soum-qwen3-4b-original:q4_k_m-bc640142`.

The control and intended smoke route share the pinned source, BF16 dequantized HF precision, F16 intermediate, Q4_K_M and Ollama template. However, a completed matched smoke artifact does not yet exist. Official-vs-control differences combine source/quantization/conversion effects and cannot be attributed to training. No control-versus-smoke agreement or quantized adapter survival can be measured yet. A future export attempt needs a verified lower-peak/streamed fusion approach or more memory headroom; do not simply repeat the same memory-heavy command.

## Bounded serving comparison

The frozen plan is four existing fictional development cases × three models = **12 maximum requests**, A-v2, temperature 0, seed 42, context 16384, output cap 1600, thinking disabled and 60-second timeout. After the smoke export failure, the plan was narrowed explicitly to its **eight official/control requests**, without substitute cases, prompt changes or retries. `--allow-missing-smoke` records the blocked third model rather than silently dropping it. A timeout records residency and stops remaining requests; a resident model alone does not prove idleness.

Requests, actual serialized messages, responses, token counts, source mappings and wall timings are in `comparison/report.json`. `scripts.pipeline4b_summary` retains invalid/time-out cases and separately reports missing relevant units, extra category assignments, all role disagreements, allergy/negation confusions and empty selections against **unreviewed provisional labels**. Source copying and valid JSON are not clinical correctness.

**Observed comparison:** all **8/8** responses were structurally valid; zero timeouts, invalid responses or all-`other` empty selections. Total measured request wall time was **120.04 s**, including model loads: official **58.02 s**, control **62.02 s**. Inputs had identical prompt-token counts for each model (2983 / 1651 / 1708 / 1754). The two models agreed exactly on **2/4** case outputs and **48/51** unit roles; this is agreement, not accuracy.

| Case | Official / control latency (s) | Observed difference |
|---|---:|---|
| DEV-002 | 25.11 / 28.57 | U12: other → explicitly-not-administered; U23: other → explicitly-not-administered |
| dev-003 | 10.93 / 11.14 | Identical roles |
| dev-004 | 10.35 / 10.57 | Identical roles, including questionable regular-use categorization |
| probe-med-001 | 11.63 / 11.74 | U4: allergy-statement → explicitly-not-administered; neither matches provisional mixed/unclear |

Against the **unreviewed** role expectations, official/control had **8/7 role disagreements**, **2/0 missed relevant units**, **2/2 extra category assignments**, and **2/2 allergy-or-negation confusions**. Counts describe this diagnostic fixture set only. The control still labels regular amlodipine as encounter-administered, treats an unasked dose as not administered, over-categorizes non-medication history, and collapses mixed/unknown patient-reported use. Clinician correction is still necessary. Both preserve literal source text; that lexical property does not fix the semantic errors. No result is attributed to training because neither serving model contains the smoke adapter.

## Clinician corrections and next quality experiment

The old canonical `expected_assignments: field → integer IDs` format describes the 19-category production task. It **cannot represent A-v2's per-unit role labels**, especially mixed/unclear, without changing the task. New `medication-role-review-1` is a versioned review envelope around the **already frozen A output**, not a new extraction schema. It retains exact source/hash/offsets, `U` IDs, labels, case/family, reviewer/date/status, correction version/superseded reference, fictional provenance and split. Original provisional files stay immutable.

Private drafts are prepared in `.runtime/pipeline4b/review-drafts` and validated/staged as **unreviewed** without a training export. No clinician corrections arrived during this work. Use the existing human review sheet; an engineer can transcribe explicit clinician corrections into the draft. The clinician need not edit JSON or token IDs. Do not infer approval from file presence.

Exact next commands after reviewed corrections arrive:

```sh
# Stage only authorized train/development contents; family registry has IDs/splits only,
# including reserved test families, never held-out note contents.
.venv/bin/python -m scripts.role_review private/role-corrections-v1.json \
  --families private/case-families.json --output private/role-stage-v1

# After explicit review of both train and development and family separation:
.venv/bin/python -m scripts.role_review private/role-corrections-v1.json \
  --families private/case-families.json --output private/role-export-v1 --export-mlx
/opt/anaconda3/bin/python -m scripts.mlx_python scripts.role_preflight private/role-export-v1
```

Exports exclude unreviewed/rejected examples, require separate reviewed train/development and reserved-test metadata, preserve mixed/unclear targets, and contain no test JSONL. They use unchanged A-v2 system/user messages plus corrected assistant labels. Outputs must stay in ignored directories; old correction versions cannot be overwritten. Previously used development families and their exact notes cannot be reassigned into train/test. Related-but-reworded family identity still requires honest human provenance; this is not a semantic duplicate detector.

**Prepared, not run:** after reviewed-data validation, resolution of the full smoke-export memory blocker, and explicit authorization for the quality experiment:

```sh
/opt/anaconda3/bin/python -m scripts.mlx_python scripts.role_train private/role-export-v1 \
  --output .runtime/role-reviewed-v1 --run-reviewed-experiment
```

Initial configuration is five steps, batch 1, rank 2, last block q/v, seed 42, Adam 1e-5, completion-only loss. All sequences are measured and checked again against exact reviewed exports; >4096 tokens stops for a new capacity assessment, never truncates. The short smoke does not establish 4096-token training capacity. Development loss is evaluated throughout and after the final step; an iteration-zero checkpoint may win, which must be reported. Held-out data is never used for selection. This reviewed-data runner is prepared/source-checked, **not exercised with reviewed data**. No automatic training follows ingestion.

Required coverage: regular vs encounter-administered vs patient-reported use; planned/prescribed vs actually given; historical courses; explicit no-treatment; allergy absence, reaction, unknown and unasked with patient attribution; mixed sentences and cross-drug associations; irrelevant non-medication facts and meaningful empty outputs. Use independent families and clinician-corrected labels. No arbitrary case count guarantees adequacy: four already-used, unreviewed cases support debugging only, not generalization; small reviewed sets support bounded diagnostics with large uncertainty.

Evaluate the selected model against its conversion-matched untuned control on the same reviewed development inputs/settings. Report role errors, unsupported additions, missed relevant units, allergy/negation/attribution errors, mixed cases, structural failures, empty outputs, timeouts and end-to-end latency. Retain exact/missing/extra assignments. Lexical source copying is not semantic validation. Have a clinician adjudicate defensible alternative roles/evidence; never repair predictions using references. Keep experimental if critical confusion, unsupported assignments, coverage gaps or latency failures remain. Propose integration only after reviewed independent-case evidence, explicit clinical/workflow acceptance, safety regressions and rollback testing; no metric threshold or loss reduction alone is sufficient.

## Offline check and user actions

The offline guide now explicitly uses a fresh `.runtime/offline-readiness-v07` bundle. A regression fixes restart configuration to use **extraction schema 0.6**, separately from **form 0.7**. Live app was not restarted. User still needs a quiet window, preserved draft, fresh bundle, manual network disconnection, cold Ollama/app restart, actual extraction→edit→approval→print, inspection of every PDF page, reconnection and recorded observations. Offline success remains unproven.
