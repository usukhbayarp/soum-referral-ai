# v0.8 partial clinician review and bounded export recovery

This milestone records **partial** decisions from **А. Балжинням, 2026-10-04**, relayed explicitly by the user. It is development diagnostics and engineering verification, not held-out evaluation, clinical validation, or quality training. Existing sources, provisional annotations, prompts, model tags and prior reports remain preserved.

## Distinct versions and application behavior

Form **experimental-0.8** renames `medical_history` to **Одоогийн өвчний түүх** and adds optional manual-only **Архаг хууч өвчний түүх** (`chronic_history`). Extraction remains **experimental-0.6**, serving prompt **source-id-v06-1**, production model **qwen3:1.7b**. The 19 extraction categories and their mapping are unchanged. Annotation revision is **clinician-partial-20261004-1**; it is separate from the original dataset annotation version.

The old extraction contract describes past medical history. Its proposal for the newly named current-illness field therefore requires explicit category reconciliation before approval. Existing manual text is preserved, never automatically moved into chronic history. The chronic field cannot be filled by the current extractor and never infers diagnoses from medication names. Both fields participate in source reconciliation, approval invalidation, case reset, late-response rejection and honest manual print attribution. Chronic history uses a full-width, wrapping print field.

Home/pre-encounter use, explicit not-given statements and relevant planned medication remain distinguishable from encounter administration. The current-history help explains this; there is no visible “Өгөөгүй эм” section. This milestone does not automatically integrate A/B outputs or use wording alone to infer who administered a drug.

## Review scope and immutable sources

`evaluation/clinician-partial-v08/annotations.json` records exact note hashes, original source version, codepoint offsets, experimental U IDs and actual original S-paragraph links where present. Unlabelled notes have null S IDs; no S IDs were invented. Each decision records its fact/category scope and supporting clinician decision. Unreviewed remainder is explicit and whole-note training eligibility is false. The original whole-note reviewed exporter rejects these partial records.

- **DEV-002:** five A-v2 labels reviewed (U11, U12, U13, U21, U23), plus specified medication facts. Regular amlodipine is distinct from administered paracetamol. Today's dose was **not asked**, not “not taken.” Frequency is not time. Patient attribution of allergy absence remains. No additional full dates are inferred.
- **dev-003:** seven category labels reviewed. U4 already reads “Уушгинд шуугиан сонсогдоогүй.” in the existing review source. This is **annotation-only**: source, IDs, hash and original case version are unchanged. It is physical examination in the full-form task and `other` in A-v2. Regular medication remains undocumented, not confirmed absent.
- **dev-004:** original U3 measurements and U4 investigation categorization are reviewed; observation phase was not approved. Home-use clarification is not scored against original predictions. Original U1/U2 labels and all source bytes remain unchanged.
- **probe-med-001:** case annotations remain unreviewed. General display rules are documented without turning them into case approval.

The same-family dev-004 clarified variant is an **implementation draft awaiting confirmation**, not a clinician quotation or reviewed training example. Exact appended wording:

> Эмчийн тодруулгын төсөл (баталгаажуулах шаардлагатай): Дээр дурдсан парацетамолыг өвчтөн энэ үзлэгээс өмнө гэртээ уусан; сумын эмч энэ үзлэгээр өгөөгүй. Амоксициллиний дурдсан курс нь өмнө гэртээ хэрэглэсэн эмчилгээ бөгөөд одоо үргэлжлүүлэн хэрэглэж байгаа эсэхийг энэ тэмдэглэл тогтоохгүй.

Its original prefix and new hash/mapping are in `dev004-clarified-draft.json`. Original and clarified variants remain in development family `fictional-004`. These already-used families may not migrate into training or final testing.

## Preserved-output re-score

No new inference was used for re-scoring. `scripts.score_partial_review` verifies exact source mapping and frozen request/contract compatibility before scoring. Prior provisional reports are unchanged.

| A-v2 model | Reviewed labels / all units | Correct | Incorrect | Unscorable |
|---|---:|---:|---:|---:|
| Preserved 1.7B | 14 / 51 | 0 | 14 | 0 |
| Preserved original 4B | 14 / 51 | 11 | 3 | 0 |
| Preserved converted control | 14 / 51 | 12 | 2 | 0 |

Coverage: DEV-002 5/33; dev-003 7/7 **category labels only**, not blanket fact approval; dev-004 2/5; probe 0/6. A-v2 roles do not expose generated drug–dose/route/time associations or generated patient-attribution statements: those dimensions are unscorable under A, not assumed correct because source quotes match.

Separate **B-v2 structured fact checks**: 1.7B **4 correct / 12 incorrect / 0 unscorable** of 16 reviewed checks; original 4B **13 / 3 / 0**. The converted control has no preserved B-v2 output and is excluded from this comparison. A and B denominators must not be combined. Original 4B still puts amlodipine frequency in administration time and fails the scoped not-asked/no-other-treatment retention checks. The 1.7B output loses paracetamol and invents medication rows in dev-003. The narrowly scoped oral-route rule accepts `уудаг`/`уусан` normalization only with the correct source-unit link and exact supporting phrase; it grants no regular-use or administration inference. Other lexical checks are unchanged.

Separate **full-form source assignment task**: available 1.7B baseline dev-003/dev-004 gives **0 correct / 8 incorrect / 1 unscorable** of 9 reviewed assignments; the grouped 1.7B design over DEV-002/dev-003/dev-004 gives **0 / 13 / 1** of 14. A category is correct only if the reviewed unit is assigned to its approved category without extra conflicting categories. dev-004 measurement phase is unscorable because the reviewer did not specify initial/current. Original-4B/control medication-role outputs cannot be reinterpreted as full-form predictions. Per-unit missing/extra categories, compatibility, raw denominators and excluded scope are saved in `reviewed-subset-results.json`.

These are partial reviewed development observations, with differing output contracts explicitly separated. They do not establish general reliability or justify a production switch.

## Lower-memory export design

Observed previous failure: full-model dequantization hit critical macOS pressure. Plausible contributors include lazy full-model allocation, retained quantized/dequantized arrays, and serialization buffers; the prior monitor cannot isolate their contributions. A first recovery-target check that loaded the full model also hit pressure 4 and was stopped at 14.55 seconds. It did not start a full revised export.

The successful targeted method initializes **only the two adapted quantized layers**, calls the installed MLX-LM `LoRALinear.fuse(dequantize=True)`, and verifies their base dequantization byte-for-byte against the existing pinned control HF artifact. It checks the independent LoRA formula and measured nonzero deltas. This avoids the full-model loader/dequantizer. MLX peak: **173,473,808 bytes (~165 MiB)**; tensor-work interval **3.59 s**. The saved three-step adapter is reused; no optimizer steps run here.

The **single revised full HF export** copies the existing verified control shards with bounded I/O buffers and replaces only those two same-shaped BF16 tensor byte ranges. It does not reinterpret or reserialize unaffected weights. All tensor names/counts/shapes/dtypes, unchanged tensor hashes, safetensors headers, shard index and replacement hashes are checked. Tokenizer/config/precision remain identical to the control. A 2-second watchdog retains critical-pressure/free-memory/RSS/contention limits; no limit was raised to force completion.

Initial measured free storage was approximately **43 GiB**; RAM remains **16 GiB**. Reusing the existing base, adapter, control HF and control GGUF means estimated *additional* storage is one new HF + F16 + Q4 + conservative Ollama copy + 2-GiB reserve: approximately **21.64 GiB**. No prior pipeline or control download is repeated, and no existing files/models are deleted. Reports and actual measurements are under `evaluation/clinician-partial-v08`.

## Observed recovery, comparison and print results

| Stage | Observed outcome |
|---|---|
| Targeted full-model load | Stopped safely at critical pressure; preserved failure report |
| Two-layer targeted fusion | Success, 165 MiB peak MLX allocation; actual saved adapter verified |
| Single revised full HF export | Success; 398 tensors checked, exactly q/v weights changed; 30.69 s supervised |
| Pinned converter → F16 | Success; 48.84 s supervised |
| Q4_K_M quantization | Success; 34.54 s supervised; final GGUF 2,497,280,320 bytes |
| Quantization survival | Exactly `blk.35.attn_q.weight` and `blk.35.attn_v.weight` differ; other 396 tensors byte-identical |
| Ollama import/inference | Success under new `soum-qwen3-4b-pipeline-test:step3-sparse-v08`; existing tags preserved |
| Matched comparison | 8/8 structurally valid, zero empty selections/timeouts; all four role outputs identical |
| Direct MLX fallback | Not needed/not attempted after recovery succeeded |

Successful recovery stages never observed critical pressure. Their highest sampled child RSS was **2.51 GiB** during quantization; the successful targeted layer job's MLX peak was **165 MiB**. These are different overlapping allocation measures and must not be added. Minimum observed system free-memory metric across successful stages was **33%**. Earlier full-model-loader failure is explicitly retained; this does not establish all full-model export approaches fit in 16 GiB.

Both imported models use the pinned source revision `52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495`, preserved template, F16 conversion and Q4_K_M settings. The control tag remains `soum-qwen3-4b-control:mlx128-52a5ab34`; the official GGUF is not substituted for this conversion-matched control. Exact model digests, requests, outputs and token counts are in `comparison-plan-imported.json` and `matched-comparison.json`.

| Case | Control / smoke total request latency (s) | Role-output agreement |
|---|---:|---|
| DEV-002 | 28.34 / 26.94 | identical |
| dev-003 | 10.59 / 10.88 | identical |
| dev-004 | 11.20 / 10.48 | identical |
| probe-med-001 | 12.59 / 12.24 | identical |

All eight request wall times sum to **123.26 s**, including loads. Small latency differences are not a speed improvement claim. Detectably changed quantized weights and identical outputs are compatible: this is a tiny three-step mechanics adapter, not a quality-trained model. Existing control errors remain. Matched untuned/adapter evaluation **now works through Ollama**; no cross-runtime MLX/Ollama quality or latency comparison was made.

Verification: **108 Python tests**, **32 JavaScript tests**, and isolated browser regression checks passed. One existing Starlette/AnyIO deprecation warning remains. Normal fictional manual print: **2 pages**; long chronic-history stress fixture: **3 pages**. All five rendered pages were inspected: no clipped/overlapping text, last line retained, legible layout, honest manual attribution and blank signature. No hard two-page limit or clinical-content approval is implied.

## Next quality-training decision

**Representation correction and independent reviewed data come first.** Frozen A-v2 cannot distinctly represent explicit home/pre-encounter use; its `mixed_or_unclear` label loses that distinction, while historical and regular roles must not be broadened retrospectively. `experiments/medication-v3-proposal/contract.json` proposes a separate `home_or_preencounter_medication` role and display mapping. It is not an active prompt, approved contract, or reinterpretation of old outputs. Mixed-source units remain explicitly mixed; a fact-level alternative would require its own clinician-approved contract.

Usable development material now consists of the scoped labels/facts above, not fully reviewed whole-note training targets. The clarified dev-004 addendum needs exact wording confirmation. Separate new training families need clinician-reviewed coverage of regular vs home/pre-encounter vs administered use, prior courses, planned/not-given medication, dose/route/frequency/time associations, not-asked versus negative statements, allergy attribution, mixed units and irrelevant/empty inputs. The four used families and all derivatives stay development. Reserve independent final-test families with metadata-only registration; do not inspect their contents for prompt design or checkpoint selection.

After contract approval and **fully reviewed separate training/development exports**, first measure every full prompt-plus-target sequence with no truncation. Measured successful training capacity is only the 1,663-token batch-one fixture. A future pilot should initially cap measured sequences at that demonstrated length (reject longer examples for capacity assessment, never truncate), batch 1, rank 2, last block q/v, learning rate 1e-5, and **one pass with an explicit ceiling of 20 optimizer steps**, whichever comes first. This is a diagnostic budget, not sufficient task training; checkpoint selection includes step zero and reviewed-development loss plus semantic error counts. Save/evaluate at most four nonzero checkpoints, keep untouched test families out of selection, and reassess budget only after capacity/coverage evidence. The prior three/five-step configurations are mechanics smoke tests, not efficacy budgets. Do not start this pilot now; no automatically executable quality run is enabled by partial review.

Compare selected candidates against the matched untuned artifact with identical runtime/template/prompt/decoding. Report correct/incorrect/unscorable reviewed facts, missing/extra assignments, regular/administered/home-use confusion, unsupported additions, allergy/negation and association errors, structural/empty/incomplete outputs, timeouts and end-to-end latency. Preserve an untuned checkpoint and baseline rollback. No lexical-match score, loss reduction, or arbitrary sample count establishes readiness. Integration requires independent reviewed coverage, adjudicated critical errors, acceptable workflow burden, safety regressions and explicit clinician/workflow acceptance.

## Human inputs and offline status

Confirm the drafted addendum wording and proposed home/pre-encounter representation; review unresolved remainder only if whole-note labels are intended. Supply separately reviewed training and development families before considering a quality pilot. Partial corrections are evaluation-only and are never exported as reviewed training rows.

No network disconnection, hosting deployment, production-model change or offline-success claim. The disconnected restart → extraction → edit → approval → print check still requires a quiet user-controlled window. The running demo is preserved; a fresh app process reads form v0.8. Print/UI QA uses an isolated local process and fictional manual fixtures.

Final measured free storage: **35.87 GiB**; pressure level **1**. The existing live demo still reports form v0.7 because it was not restarted; v0.8 was verified in the isolated fresh process. Activate it during a user-chosen quiet restart so an open referral is not lost.
