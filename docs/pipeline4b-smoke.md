# Original-4B pipeline verification — bounded engineering milestone

**Observed partial success, not clinical improvement.** Actual three-step adapter training, exact adapter reload, adapter inference and adapter-layer fusion succeeded. Full export/control/serving comparison is **disk-blocked**. No production app/model/prompt/form changes; no training on the four unreviewed development cases, held-out content access, cloud deployment or network disconnection.

## Source and compatibility

Training checkpoint: [official Qwen/Qwen3-4B-MLX-4bit](https://huggingface.co/Qwen/Qwen3-4B-MLX-4bit/tree/52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495), revision **52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495**. Tokenizer/config come from that same revision. All downloaded files have recorded SHA256; the 2,137,326,367-byte model matches the publisher LFS hash. This is the original dual-mode text-only family, not Thinking-2507 or VL. The exact original full-precision weight revision used to make this official MLX artifact is unpublished; no numerical equivalence with the official GGUF is asserted.

Quantization: 4-bit affine, group size **128**, actual floating tensors **BF16**. Official config differs from the separately inspected HF/GGUF metadata (65536 context, max-window-layers 28, but 36 actual model layers); these differences are recorded, not rewritten. The short smoke exercises 1663 tokens, not maximum context. Publisher card's license link points to a 14B page; the actual repository LICENSE was downloaded and records Apache-2.0. Keep that notice with redistributed artifacts.

Reused versions: MLX **0.30.6**, MLX-LM **0.30.7**, Transformers **5.2.0**, huggingface-hub **1.4.1**. No second stack installed. The existing noninteractive readline workaround is reused. Installed Qwen3 loader, LoRA utilities and [MLX-LM fuse implementation](https://github.com/ml-explore/mlx-lm/blob/v0.30.7/mlx_lm/fuse.py) were inspected and exercised. Converter remains llama.cpp **11fe02151f79c41d0d4af7da708755d73b9c0da6**; planned route is BF16 dequantized HF-compatible weights → llama.cpp F16 GGUF → Q4_K_M → Ollama with the preserved template hash. **Never use MLX's unsupported built-in Qwen GGUF exporter.**

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
| Full dequantized HF artifact | Not attempted: disk guard rejected before allocation |
| GGUF conversion / Q4_K_M | Not attempted: depends on disk-blocked artifacts |
| Matched untuned control / smoke Ollama imports | Not attempted; no new tags created |
| Three-way serving comparison | Not attempted, **0/12 requests**; missing control and smoke imports |

Separate fictional fixture `training/engineering4b-fixture.json` is AI-created, unreviewed and permanently engineering-only. It never passed through the clinician-reviewed exporter. Its source is rejected by the clinical correction workflow even if someone changes its ID/review status. Initial and final adapter tensors remain local under `.runtime/pipeline4b/smoke`; no weights are committed. No clinical candidate was created or promoted.

The supervised subprocess took **50.63 seconds** including startup/hash checks; measured model-work interval **36.84 seconds**. MLX peak allocated bytes **4,415,189,868 (~4.11 GiB)**; two-second child RSS peak **2,078,608 KiB (~1.98 GiB)**. These overlap; do not add them. System free-memory metric stayed at least 27%; macOS pressure levels 1 and 2 were observed, never critical 4. The watchdog did not intervene. Hard MLX allocation limit 8 GiB, RSS stop 9 GiB, critical-pressure/free-percentage guard, 600-second job bound and Ollama-residency guard applied. Only the owned child could be stopped; the app and shared Ollama service were not restarted.

## Disk blocker and prepared matched control

Observed free space: **9.5 GiB before download**, about **6.3 GiB after the smoke** (system-wide free space fluctuates). Each dequantized full model/F16 GGUF is estimated at **7.49 GiB** from 4,022,468,096 parameters. Keeping both pipelines' new HF/F16 intermediates, both Q4 files, conservative Ollama blob copies and a 2-GiB safety reserve requires **41.27 GiB still free after the MLX base is present**. The executed guard reported **6.26 GiB free: add 35.01 GiB**. This is an estimate, not a measured export peak.

Sequential disposal of only newly generated, hashed intermediates could lower remaining free-space needs to about **26.29 GiB** (roughly **20 GiB more** than currently free). That cleanup strategy is not implemented or executed; no existing artifacts/caches/models were deleted. Supply additional free space or an explicitly chosen sufficiently large working volume before resuming.

`sh scripts/pipeline4b_export.sh` is a **prepared, not end-to-end tested** recipe with source/adapter hashes, converter pin, disk/residency checks and overwrite refusal. Its guard was actually run and refused safely; it did not invoke fusion/conversion/import. Both planned outputs use the same pinned MLX checkpoint, BF16 HF precision, F16 intermediate, Q4_K_M and preserved Ollama template. Planned tags (not installed):

- `soum-qwen3-4b-control:mlx128-52a5ab34`
- `soum-qwen3-4b-pipeline-test:step3-52a5ab34`

Existing official comparator remains `soum-qwen3-4b-original:q4_k_m-bc640142`. Existing baseline/rollback tags are unchanged. The official artifact is a reference, not the MLX conversion-matched control. Official-vs-control differences would include source/quantization/conversion effects; only matched-control-vs-smoke could isolate the effect of this adapter, and neither establishes clinical improvement.

Comparison is predeclared in `evaluation/pipeline4b-smoke/pins.json`: all four existing fictional development cases, frozen A-v2, each of three models once = **12 requests maximum**, original 60-second/options limits, no retries. `scripts.pipeline4b_compare` saves every request/response/validation/timing. A timeout checks model residency; because residency does not prove idleness, the runner stops all remaining work rather than launching another heavy job. Imported digests must be filled by the guarded export recipe before comparison can run.

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

**Prepared, not run:** after reviewed-data validation, more disk, a verified matched control, and explicit authorization for the quality experiment:

```sh
/opt/anaconda3/bin/python -m scripts.mlx_python scripts.role_train private/role-export-v1 \
  --output .runtime/role-reviewed-v1 --run-reviewed-experiment
```

Initial configuration is five steps, batch 1, rank 2, last block q/v, seed 42, Adam 1e-5, completion-only loss. All sequences are measured and checked again against exact reviewed exports; >4096 tokens stops for a new capacity assessment, never truncates. The short smoke does not establish 4096-token training capacity. Development loss is evaluated throughout and after the final step; an iteration-zero checkpoint may win, which must be reported. Held-out data is never used for selection. This reviewed-data runner is prepared/source-checked, **not exercised with reviewed data**. No automatic training follows ingestion.

Required coverage: regular vs encounter-administered vs patient-reported use; planned/prescribed vs actually given; historical courses; explicit no-treatment; allergy absence, reaction, unknown and unasked with patient attribution; mixed sentences and cross-drug associations; irrelevant non-medication facts and meaningful empty outputs. Use independent families and clinician-corrected labels. No arbitrary case count guarantees adequacy: four already-used, unreviewed cases support debugging only, not generalization; small reviewed sets support bounded diagnostics with large uncertainty.

Evaluate the selected model against its conversion-matched untuned control on the same reviewed development inputs/settings. Report role errors, unsupported additions, missed relevant units, allergy/negation/attribution errors, mixed cases, structural failures, empty outputs, timeouts and end-to-end latency. Retain exact/missing/extra assignments. Lexical source copying is not semantic validation. Have a clinician adjudicate defensible alternative roles/evidence; never repair predictions using references. Keep experimental if critical confusion, unsupported assignments, coverage gaps or latency failures remain. Propose integration only after reviewed independent-case evidence, explicit clinical/workflow acceptance, safety regressions and rollback testing; no metric threshold or loss reduction alone is sufficient.

## Offline check and user actions

The offline guide now explicitly uses a fresh `.runtime/offline-readiness-v07` bundle. A regression fixes restart configuration to use **extraction schema 0.6**, separately from **form 0.7**. Live app was not restarted. User still needs a quiet window, preserved draft, fresh bundle, manual network disconnection, cold Ollama/app restart, actual extraction→edit→approval→print, inspection of every PDF page, reconnection and recorded observations. Offline success remains unproven.
