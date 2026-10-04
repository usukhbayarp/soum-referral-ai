# Original Qwen3-4B medication comparison + v0.7 handoff

**Observed mechanics on four fictional, unreviewed development cases. Not clinical validation, held-out evaluation or proof of reliability.** No training, production extractor replacement, paid deployment, disconnected test or submission occurred.

## Decision

**Neither A nor B is ready for integration.** The next bounded candidate is **original Qwen3-4B / A / medication-A-2**, using clinician-corrected labels and new reviewed development families. It completes within the limit and has fewer provisional role errors than either 1.7B prompt. Keep all treatment-table transcription manual. B-v2 is worth retaining as a secondary research/training option: it recovers some correct values but needs semantic-link corrections and fails the time bound on the mixed probe. Do not infer that increasing the model size solves extraction.

There is insufficient evidence to extend this result to the broader 19-category v0.7 proposal mapping. First establish narrow medication/allergy behavior with reviewed labels, including regular vs administered, mixed sentences, unasked/negative statements, historical courses, planned/not-given drugs and patient attribution. Fine-tuning is a plausible follow-up for these repeatable errors; it is not ruled out by the deadline and has not been attempted.

## Identity and frozen comparison

[Provenance, license, tokenizer and limitations](PROVENANCE.md). Official Qwen Q4_K_M file hash verified; new tag `soum-qwen3-4b-original:q4_k_m-bc640142`. Upstream metadata revision inspected: `1cfa9a7208912126459214e8b04321603b3df60c`; artifact revision `bc640142c66e1fdd12af0bd68f40445458f3869b`. Internal `Instruct-awq` label and unpublished conversion input revision are explicitly disclosed. Existing `qwen3:4b` remains Thinking-2507 and was **not used**.

The 1.7B baseline remains digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`. No 1.7B inference was repeated. New reports record exact original-4B digest, full serving template, raw wire requests/responses and source maps. Contract `medication-representation-1`, prompts `medication-A-1/B-1/A-2/B-2`, source IDs, expectations and strict validators are unchanged. Post-run checks compare every new request to its original 1.7B request, allowing only `model` to differ. No answer labels enter requests.

All calls: `think:false`, `temperature:0`, `seed:42`, `num_ctx:16384`, `num_predict:1600`, `stream:false`, `keep_alive:"5m"`, 60-second deadline. Alternating A/B order matches the original. DEV-002 A/B repeat used **v1, predeclared before inference**. No favorable retries or limit increases. Timeout entries retain the exact request/error/time; no response body or server termination reason was received, so these are unavailable rather than invented.

## Mechanical results, first runs only

The 51 source units contain **16 provisionally relevant medication/allergy units** and 35 other units. Exact agreement below is against frozen, unreviewed expectations, not clinician-assessed correctness. Mixed/unclear remains a review assignment, never successful structured extraction. All missing/extra IDs by role and raw differences are in `summary.json`.

| Model / prompt | A structural | A exact all units | A exact relevant units | B structural | B strict evidence-valid |
|---|---:|---:|---:|---:|---:|
| 1.7B v1 | 4/4 | 15/51 | 2/16 | 4/4 | 0/4 |
| 1.7B v2 | 4/4 | 6/51 | 5/16 | 4/4 | 0/4 |
| Original 4B v1 | 4/4 | 42/51 | 7/16 | 2/4 | 1/4, **empty response** |
| Original 4B v2 | 4/4 | 43/51 | 10/16 | 3/4 | 1/4, dev-003 |

Including repeats, original 4B produced **14/18 structural passes, four timeouts**. Nine A outputs are structurally/evidence valid by their source-copy design, but role errors persist. Of nine B attempts: four timeouts, three strict-evidence failures, two strict passes; one pass is an empty abstention that omits relevant facts. All returned envelopes stopped normally without reasoning. No dropped failures or partial acceptance. Original 4B A-v1 DEV-002 repeat is byte-identical; B timed out twice, so content repeatability is **unknown**, not “identical.” Original 1.7B A/B v1 repeats were byte-identical; one repeat does not establish determinism.

## Semantic audit and remaining clinician work

| Case | Original 4B A v1 → v2 | Original 4B B v1 → v2 | Remaining review/transcription |
|---|---|---|---|
| DEV-002 | Regular amlodipine labeled planned → administered. Both omit today's-dose-unasked and no-other-treatment context. Allergy omitted in v1, correctly selected in v2. V2 also mislabels complaint/history as medication roles. | V1 timeout twice. V2 gets regular amlodipine and administered paracetamol roles, paracetamol dose/route/time/frequency and intact patient-reported allergy absence. It puts `уудаг` in amlodipine route and `өдөрт 1 удаа` in time; missing unasked/no-other context as explicit context outputs (unasked text exists only in linked evidence). | Correct amlodipine grouping/detail types; add omitted context; verify patient attribution and time-only date uncertainty. A supplies no structured table values: all table entry remains manual. B-v2 has four provisionally retainable paracetamol detail slots after review, but no whole-output acceptance. |
| dev-003 | V1 calls allergy/no-treatment “other”; v2 matches all provisional roles. | V1 empty arrays: strict pass but complete omission. V2 preserves allergy absence and no-treatment; adds no-investigation text into medication context. | Review the two distinct negative statements; remove/move out-of-scope investigation context. Do not invent a drug row for “no treatment.” |
| dev-004 | Both incorrectly call patient-reported paracetamol taking regular use; historical amoxicillin and allergy are selected correctly. | V1 regular paracetamol with tablet wording as route/count as frequency; historical amoxicillin frequency as route and five-day duration as time; adds a false not-administered penicillin medication row with rash words as dose/route/time. V2 removes that false row but calls paracetamol encounter administration, uses tablet count as route, invents `1 удаа`, and repeats amoxicillin route/time mistakes. Both preserve intact penicillin-rash allergy. | Correct medication role and dose/tablet quantity; clear unsupported route/frequency; distinguish course duration from event time. Preserve rash allergy and historical duration; remove unrelated vitals/glucose from v2 medication context. |
| probe-med-001 | Both select only regular use for the mixed regular/administered sentence and misclassify unnamed medication use as allergy. Planned ibuprofen, explicit non-administration and both allergy uncertainty statements are selected correctly. | Both versions time out at 60s; no usable structured result. | Split mixed roles manually; preserve each drug's own dose/route/time/frequency, planned/not-given distinctions and unnamed-drug uncertainty. No successful B result can be inferred. |

Baseline 1.7B had worse role organization and all B outputs failed strict evidence validation. Representative earlier errors remain visible in the side-by-side sheet: regular amlodipine labeled administered/planned; planned ibuprofen labeled administered; paracetamol time/frequency borrowed across drugs; unknown/no-treatment placeholders; v2 dev-004 allergy rewritten as absence despite documented penicillin rash. Existing full audit is preserved at `docs/medication-representation-comparison.md`.

**Lexical versus factual:** 4B B-v2 DEV-002 `Парацетамол` vs source lowercase `парацетамол` is a capitalization-only mismatch. Similar capitalized drug names occur in dev-004. The strict validator still fails these; no output or reference is repaired. By contrast, truncated context missing `10:15-д`, invented frequency, duration-as-time, frequency-as-route and incorrect regular/administered relationships are substantive omissions/type/association errors. Some are lexically supported by the same quote and therefore are not caught by strict quote checks. V1 mixed Latin/Cyrillic `paraцетамол` also needs exact-source correction; do not normalize it silently.

## Total request latency, seconds

`T` = timed out, censored at the deadline, not a completed inference. Order is DEV-002 / dev-003 / dev-004 / probe; each value includes the complete request, not a fastest subcall.

| Model/prompt | A | B |
|---|---|---|
| 1.7B v1 | 24.412 cold / 1.917 / 1.357 / 1.905 | 16.815 / 18.613 / 12.957 / 27.886 |
| 1.7B v2 | 13.018 / 2.149 / 1.568 / 4.095 | 13.091 / 12.347 / 29.483 / 34.348 |
| Original 4B v1 | 24.528 cold / 4.715 / 3.460 / 4.854 | 60.005 T / 2.323 empty / 43.634 / 60.001 T |
| Original 4B v2 | 24.968 / 4.144 / 3.102 / 4.439 | 47.623 / 12.985 / 32.717 / 60.002 T |

Original 4B v1 DEV-002 repeats: A 21.312s warm; B 60.003s timeout. Prior 1.7B repeats: A 10.286s, B 15.701s. First 4B A load/prompt/generation: **2.854 / 6.553 / 15.084s**; repeat **0.004 / 6.279 / 14.996s**. Per-call component timings and token counts remain in raw reports (unavailable for timeouts). The 18-request run window was **08:46:59.829–08:54:55.020 UTC, 475.191s**; no other local inference was launched by this milestone.

Two-second samples: Ollama `size_vram` peak **5,050,204,159 bytes (~4.70 GiB)**; largest runner RSS **3,038,480 KiB (~2.90 GiB)**. These overlap and must not be added. System free-memory metric 51% before / 19% after comparison. No observed OOM; that is not a peak physical-memory measurement or a 4B training-fit guarantee. Disk after download/import: about 6.2 GiB free. Another full-precision 4B checkpoint/export needs more disk; no cache deletion or such download was attempted.

## Form, review and training handoff

[v0.7 form mapping/checks](../../docs/v07.md): 72 fields, six sections, 19 unchanged extraction proposal categories. The live app serves v0.7. Production remains **qwen3:1.7b / source-id-v06-1 / experimental-0.6 extraction**, local mode; no extraction defaults changed. Only the project web process was restarted; Ollama/unrelated services were not. Existing tabs retain their memory-only old draft; preserve it before reload. Fresh tabs receive v0.7.

Open [clinician review sheet](clinician-review.html), then [annotation guidance](ANNOTATION.md). Draft annotations remain unreviewed, development-only and ineligible for training. Correct the expected labels as well as proposals, record reviewer/date/explicit status, and keep used development families out of held-out tests. No held-out content was opened.

Existing MLX environment, masking/length checks, family/review gates and 1.7B export tooling are reusable. [Training compatibility](../../docs/training.md) distinguishes source-inspected Qwen3 LoRA support from untested 4B allocation/training/fusion/export. Full sequences measured up to **4081 tokens**, not silently truncated to 256–512. Original publisher GGUF is **not** a future MLX conversion-matched control; create that control before evaluating any tuned 4B. Keep every base/rollback tag.

Focused checks verify identity/smoke, exact frozen request equality, response replay, offsets/repeated quotes, form/API versions, case/reconciliation/approval safety, optional print rows, pending/transport/oxygen conditions, and preserved historical files. Normal print **2 pages**; stress print **3 pages**; all pages visually inspected. Human sheet checked at desktop and narrow widths with exact original source and blank review fields. See `verification.json` for final counts/proof.

Offline restart, hosting/provider/budget, clinical validation, time-saved measurements and submission remain pending. Videos: **exactly three separate videos, each ≤60 seconds: Team Intro, Demo, Teach**. No training automatically starts when files arrive; the next step is clinician adjudication and validation of separately supplied reviewed train/development material.
