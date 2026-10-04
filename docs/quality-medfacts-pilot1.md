# Four-step diagnostic pilot — observed results, 2026-10-04

**Recommendation C: neither the untuned control nor either checkpoint is useful enough for this source-linked fact task.** Four optimizer steps changed weights, and both checkpoints survived verified export and quantization. All three development responses were identical to the untuned baseline at both checkpoints. No reviewed-development improvement or clinical usability was demonstrated. This tiny result does not establish fine-tuning's overall potential.

Production remains `qwen3:1.7b` / `source-id-v06-1`. No model was promoted, no application settings changed, and the live port-8000 process still reports **experimental-0.7**. The implemented v0.8 interface/history fix was not activated by restarting it. No offline/disconnected test, hosted deployment, final-test evaluation or submission occurred.

## Frozen scope and actual training

Starting main: `e125ad3aa36420d5f7d067f9f0a814a063e9c4ed`, clean. Source notes, scoped approved mappings, family separation, export, tokenizer/base, contract/prompt, baseline model/template and converter pins passed integrity checks. No new cases were added; final-test contents stayed unopened. The two approved fictional families remain train-only; development uses only the nine approved facts from the same three existing notes. Whole-target development loss remains unavailable.

The existing MLX 0.30.6 / MLX-LM 0.30.7 environment was reused. Frozen source/tokenizer: **Qwen/Qwen3-4B-MLX-4bit@52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495**, affine 4-bit/group 128. Contract **source-linked-medfacts-1**, prompt **medfacts-1**, unchanged. Actual full sequences remained 2690 and 2727 tokens; completion-only masks and no-truncation checks passed.

Exactly **four** Adam updates ran, batch one, seed 42, learning rate 1e-5, rank two, last-block q/v, two passes, with gradient checkpointing, 8-GiB MLX and 128-MiB cache limits. The existing watchdog limits were not raised. Finite losses and gradients were checked before every update. Both checkpoints saved after steps 2 and 4 reloaded with exact parameter equality. All four LoRA A/B arrays changed from initialization; final maximum absolute array changes were 0.000118–0.000178. Training telemetry is in `evaluation/quality-medfacts-pilot1/training.json`.

| Step | Training family | Completion loss | Full / completion tokens |
|---|---|---:|---:|
| 1 | TRAIN-001 | 0.373588 | 2690 / 708 |
| 2 | TRAIN-002 | 0.357746 | 2727 / 710 |
| 3 | TRAIN-001 | 0.374294 | 2690 / 708 |
| 4 | TRAIN-002 | 0.357570 | 2727 / 710 |

There was no consistent loss reduction across passes. Loss is a training diagnostic, not a clinical result. Training took **76.43 s supervised**, including integrity/load overhead; the model/training interval was about **64.34 s**. Peak MLX allocation **5,666,708,000 bytes (5.28 GiB)**, peak sampled training child RSS **2.45 GiB**, minimum sampled system free-memory metric **17%**. Pressure levels 1 and 2 occurred; no critical level 4, nonfinite values or guard termination occurred. These memory measures overlap and must not be added.

## Verified export and retained artifacts

Each checkpoint was processed sequentially: enumerate all adapter A/B pairs → targeted installed MLX-LM fusion → verified control-HF byte replacement → pinned llama.cpp F16 → Q4_K_M → new Ollama tag. No full-model MLX dequantization or unsupported built-in Qwen GGUF export was used.

All 398 HF tensor names/indexes/shapes/dtypes were checked. Base dequantization matched the pinned control, and fusion matched the explicit base-plus-adapter formula. Only the adapted last-block q/v weights changed; the other 396 tensors stayed byte-identical. F16 verification compared **every value of all 398 tensors** against the BF16 HF source, using the pinned converter's tensor-name map. Both Q4 artifacts retain changed q/v tensor bytes, with every other tensor equal to the control.

Converter commit: **11fe02151f79c41d0d4af7da708755d73b9c0da6**, clean checkout. Actual quantizer binary hash, commands, stage timings, memory samples, artifact hashes, templates and imports are recorded under `evaluation/quality-medfacts-pilot1`.

| Checkpoint | Adapter SHA-256 | Final Q4_K_M SHA-256 |
|---|---|---|
| 2 | `e340e81cc60feeb97610ec1373140f7c089900067625e989477171a2ee5ccbea` | `39dbd9aafec79ab55e93945ac62f9e49c4d7269feeb7ac9d4c92531fa816c3e6` |
| 4 | `56d566bca5caecf55c2d2cdb2aff0cf8a6dce581f16fe06fb5d0605e9f2b8a15` | `60dd20aaeba455781ff060d2f5a97186733d610ee4368bf1c7a86ded68f79f5c` |

Retained adapters/configurations: `.runtime/quality-medfacts-v1-pilot/step-2` and `step-4`. Retained final artifacts: `.runtime/quality-medfacts-v1-step2/candidate-Q4_K_M.gguf` and corresponding `step4` path, each **2,497,280,352 bytes**. Both Ollama tags/runtime blobs remain available:

- **soum-qwen3-4b-medfacts:pilot1-step2**, digest `76249ac3b5f580251328d34c8c1bb08ec285d203824ec8c6bb8a01ea8bdfb50f`.
- **soum-qwen3-4b-medfacts:pilot1-step4**, digest `476c1eddc6d929c4adaec05dabd2f5c0462fb1f22e2d8fe269e92744b5766a02`.

All existing tags/digests remain unchanged. Only the pilot's completed experimental models were unloaded through Ollama's supported empty-request/keep_alive=0 mechanism between/after evaluations. The shared service was not restarted.

One tooling failure was preserved: the first F16 verification attempt raised `ModuleNotFoundError: No module named 'gguf'`. The helper was corrected to import the pinned checkout's bundled `gguf-py`, matching the converter's approach. Verification resumed against the existing converted artifact under a new watchdog report. Training, conversion and development inference were not repeated to obtain a passing result. `verification-import-error.txt` and the failed watcher report remain.

## Matched development results

Exactly **six new development requests**: three per checkpoint, one attempt each. Step zero reuses the preserved baseline; no baseline rerun, sweep or reference-based repair. Requests match after removing only the model identifier: same full notes, explicit scope, prompt/contract, output schema, template, temperature 0, seed 42, context 16384, output bound 3200, think=false and 120-second timeout. The engineering smoke model was never a baseline or quality candidate.

| Model | Correct / all 9 | Incorrect or missing | Unscorable from invalid output | Contract/evidence-valid / 3 | Total request latency |
|---|---:|---:|---:|---:|---:|
| Untuned control | 1/9 | 4 | 4 | 1/3 | 26.93 s |
| Step 2 | 1/9 | 4 | 4 | 1/3 | 24.10 s |
| Step 4 | 1/9 | 4 | 4 | 1/3 | 26.33 s |

Per model: **zero empty, token-limit-truncated or timed-out responses**; one valid but semantically incomplete response; two invalid responses. All nine facts remain in the denominator. The small latency differences are not evidence of a speed improvement.

| Input | Prompt/output tokens, all three models | Untuned seconds | Step 2 seconds | Step 4 seconds |
|---|---:|---:|---:|---:|
| DEV-002 | 2727 / 64 | 14.85 | 12.98 | 13.89 |
| dev-003 | 1476 / 146 | 8.17 | 7.60 | 8.41 |
| dev-004 | 1535 / 44 | 3.91 | 3.52 | 4.02 |

Raw assistant contents are identical to baseline for every input at both checkpoints:

- **DEV-002:** retains regular amlodipine only. Missing reviewed facts: today's dose not asked, patient-reported allergy absence, administered paracetamol and no-other-treatment. A context link to U12 does not substitute for preserving the not-asked fact. A doctor must still add these four facts and verify attribution and medication roles.
- **dev-003:** merges allergy absence, no treatment and no investigation into one medication fact, with incompatible regular/home/administered/historical/stopped/planned/not-administered and uncertainty attributes. This is not defensible merely because the three quotations exist. The contract rejects it; all three reviewed facts remain unsuccessful/unscorable outcomes, not dropped from the denominator.
- **dev-004:** returns the literal prompt placeholder **яг эхийн хэсэг**, linked to U1, instead of actual source evidence. The investigation fact remains unscorable; the unsupported quote is rejected.

No unmatched extra facts occur in the sole valid response. Invalid raw outputs are retained separately with errors; their extra claims are not assigned invented reference labels. Reviewed exact-span metrics and overlap alternatives keep their existing limitations. This is partial reviewed development, not complete-referral quality or generalization evidence, and it must not be compared numerically with earlier A-v2 role-label scores as the same task.

The unchanged selector retains the untuned baseline on the tie, **only as an advisory diagnostic**. It does not establish that the baseline is clinically usable or justify integration.

## Cleanup, verification and decision

Deleted **29.98 GiB** total across both checkpoints: only newly generated candidate HF weight shards after verified F16 conversion and candidate F16 GGUF after verified Q4 quantization. Each deletion has source/downstream hashes, byte counts and a completion record. No base/control/historical artifact, adapter, final Q4, model tag, cache or unrelated file was deleted. Final measured disk free: **27.10 GiB**. The full recorded run from frozen preflight through final verification took about **10.2 minutes**; per-stage measurements are in the reports. Highest sampled child RSS across watched stages was **4.49 GiB**, during Q4 verification; this is separate from MLX allocation and excludes an inference-process peak measurement.

**11 focused tests passed**, including review/export preflight, adapter enumeration, matched selection and cleanup guards. Runtime training/reload/fusion/HF/F16/Q4 checks also passed. No unrelated full browser audit was repeated. Only logging and new orchestration/verification helpers changed; the training algorithm, frozen prompts/data/contract, scoring, production UI and settings did not change.

Separate conclusions:

| Question | Observed answer |
|---|---|
| Weights changed? | Yes; four optimizer updates and two verified saved adapters |
| Changes survived export/quantization? | Yes; q/v tensor bytes differ in both final Q4 artifacts |
| Predictions changed? | No, all six new assistant responses equal their baseline counterparts |
| Reviewed development outcomes improved? | No, all remain 1/9 correct and 1/3 valid |
| Clinical usability demonstrated? | No |

**Smallest next change:** a separately authorized review-only trial that asks for exact source snippets for **one doctor-selected field**, leaving destination/status classification and acceptance explicit with the doctor. Reuse deterministic source IDs and existing evidence/reconciliation controls; do not expand the form/schema or integrate either tuned checkpoint. Clinician review should check snippet relevance, preserved negation/attribution, omissions and actual correction burden on existing development notes before broader use. These results do not justify another training sweep or a claim that a more substantial learning experiment cannot work.

Remaining delivery work is separate: safely activate the already implemented v0.8 UI when an application restart is appropriate, obtain broader independent clinician-reviewed evaluation/final-test material, perform an explicitly scoped offline acceptance test, and resolve any hosting/submission requirements. None was completed or claimed by this pilot.
