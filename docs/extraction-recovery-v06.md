# Bounded extraction recovery, 2026-10-04

**Observed outcome: neither tested candidate is usable for broad v0.6 automatic field assignment. No runtime default changed.** This is an unreviewed, fictional development investigation, not clinical validation. The application remains on `qwen3:1.7b`, `experimental-0.6`, `source-id-v06-1`, local deployment. No training, model download, model-tag modification, paid deployment or network-disconnected demonstration was performed. Existing prompts, schema, baseline reports and source files are unchanged.

## Input, identity and scoring audit

The first new inference was the existing v0.6 DEV-002 task on the installed 4B tag. [Its wire capture](../evaluation/recovery-v06/baseline-4b-dev002.json) comes from the actual application adapter via a read-only HTTP transport wrapper. It retains the serialized JSON request, raw runtime envelope, model information and template. Later calls retain the same information in their report's `calls` entries. Historical 1.7B DEV-002 output was reused, not rerun or repaired.

Observed identities on Ollama **0.34.0**, both Q4_K_M:

| Tag | Observed metadata | Digest |
|---|---|---|
| `qwen3:1.7b` | GGUF size label 1.7B; runtime reports 2,031,739,904 parameters / 2.0B in tag details | `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| `qwen3:4b` | `general.finetune=Thinking`, `general.version=2507`, 4,022,468,096 parameters; license link identifies Qwen3-4B-Thinking-2507 | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |

The original single-call request has 19 headings, plus `{id,start,end,text}` for all 33 units. The original `[S01]`–`[S11]` markers remain inside `text`; they identify clinician paragraphs, **not** the integer units. For example S04 maps to units 14–18, S06 to 21–23, and S01 to 1–5. This makes two numbering systems and offset numbers visible to the model. Resolution itself has no observed off-by-one problem: selected integers retrieve the exact original unit, with `note[start:end] == text`. Expected assignments agree with the preserved clinician paragraph mapping; neither assignment scoring nor evidence resolution interprets `[Sxx]` as an integer ID.

All requests use `stream:false`, `think:false`, `keep_alive:0`, temperature 0, seed 42, context 16384 and maximum output 1600. The stored model defaults include temperature 0.6, top_k 20, top_p 0.95, repeat_penalty 1 and stop tokens; explicit request temperature overrides the stored temperature. Both actual templates and these stored parameters are captured.

**Documentation-supported limitation:** [Qwen's Thinking-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507) says this checkpoint supports only thinking mode and its template opens `<think>`. The installed 4B template does indeed open `<think>` without the standard 1.7B non-thinking branch. The 1.7B template has a `/no_think` branch and an empty thinking block. The installed API accepted our `think:false` 4B request and returned JSON with no separate thinking content and `done_reason:stop`; this does **not** establish supported non-thinking operation for Thinking-2507 or equivalence to standard Qwen3-4B. See also [Ollama's chat request/response documentation](https://docs.ollama.com/api/chat). We did not patch the template or run another mode experiment.

The audit captures API messages and the installed template, not Ollama's internal post-template token stream. Exact low-level template/parser interaction remains unverified. This compatibility caveat prevents treating the 4B result as a clean size-only comparison.

## One simplification, isolated from serving

[`grouped-source-id-v06-1`](../experiments/recovery-v06/grouped-source-id-v06-1.json) partitions the same 19 selection fields into five calls: identity/history/assessment; regular and administered medication/allergies/pain change; initial/current/examination; investigations/attachments/pending; referral/action/plan. All 67 editable form fields remain unchanged. The group design uses existing field instructions with their Mongolian labels; empty selections are permitted. Every call receives **all source units**, including negatives and temporal context. Detailed dates, doses, observations and treatment rows stay manual in the application.

Presentation version `integer-only-source-view-1` removes only an anchored `[S<number>]` marker and adjacent following whitespace from model-facing unit text, using a generic rule; it drops start/end from the model payload. It retains the original integer IDs. No clinical words, original note, segmentation, offsets or stored evidence are changed. Captures include both the original units and the presentation so this is reviewable. Source text is never reconstructed from the simplified view. No DEV-002 assignment is encoded in the prompt or supplied to the model. Expected labels are used only **after** generation for scoring.

All groups must validate strictly before an atomic combined result is accepted: exact keys, strict integer IDs, known unique IDs, no duplicate JSON keys. Failure is recorded as failure, not empty selections. There is no answer-key repair, permissive partial acceptance, field-specific fallback or majority vote. This is a single combined simplification, **not an ablation**: it cannot isolate the effect of grouping from removing offsets/markers or using bilingual headings.

DEV-002 grouped prompt counts were 1829, 1823, 1756, 1738 and 1803 tokens (8,949 across five calls); output counts 505, 334, 342, 179 and 36. All stopped normally. It consumed **76.836 seconds end to end**, including all five requests, model loads/unloads, parsing and validation, not the fastest group. The unchanged baseline 1.7B DEV-002 prompt was 2,624 tokens. There was no silent source truncation or context/output-bound increase.

## DEV-002 results

All labels remain **provisional/unreviewed**, all data fictional and development-only. “Exact” below means equality with a source-ID set, not clinical accuracy. Missing/extra counts are **field–ID pairs**, so one ID assigned incorrectly to multiple fields is counted multiple times. Full per-field expected/actual/missing/extra arrays and abstentions are in [summary.json](../evaluation/recovery-v06/summary.json).

| Candidate / prompt | Structure | Exact sets / 19 | Missing pairs | Extra pairs | Total latency | Abstaining fields |
|---|---|---:|---:|---:|---:|---|
| Preserved 1.7B / `source-id-v06-1` | Valid | 1 | 18 | 117 | 29.324 s | None |
| Installed 4B Thinking-2507 / `source-id-v06-1` | Valid | 2 | 24 | 5 | 54.745 s | comorbid, allergies |
| Grouped 1.7B / `grouped-source-id-v06-1` | Valid, all five calls | 0 | 13 | 235 | 76.836 s | attached, pending_results, referral |

Observed errors and remaining manual corrections:

- **Preserved 1.7B:** regular medication includes administered paracetamol/response and omits “today's dose not asked”; treatment includes amlodipine. Initial observations select current vital unit 25 and omit initial vital unit 15. Allergy, assessment, comorbidity, requested action, attachments and plan select “no pending results.” The initial pain unit is missing. A clinician would need to reconstruct almost every narrative grouping, preserve negatives and attribution, and enter the manual administrative, observation and treatment details. Original output remains [unchanged here](../evaluation/dev002-v06/results/comparison-20261004T071312Z.json).
- **4B:** complaint selects only unit 6, losing morning stiffness and denied trauma/fever (7–9). Regular medication selects 11 but loses unasked-today-dose 12; medical history incorrectly selects medication 11 rather than hypertension 10. Assessment selects comorbid hypertension 27 instead of assessment 26; allergies/comorbidity abstain. Initial/current select times/condition 14/24 but omit vital units 15/25; examination omits range not assessed and pain 17/18. Investigations omit tests not performed 20, while pending incorrectly selects 20 rather than explicit no-pending 33. Attached selects results 19 instead of attachment statement 32. Treatment selects 21 but loses response/no-other-treatment 22/23; pain change includes 22 without initial 18. Plan selects referral 29 rather than follow-up 31. The clinician still must restore these omissions, correct the categories and fill manual subfields. Requested action 30 and explicit referral type 29 matched; this is insufficient for broad use.
- **Grouped 1.7B:** identity and complaint each select all 33 units. Regular medication, treatment, allergy and pain change repeat the same unrelated range including regular and administered medicines; regular medication still omits 12, allergy omits 13, pain change omits 18. Initial/current repeat the same large set, include both initial and current vitals and omit initial condition/time 14; examination omits “not assessed” 17. Investigations select all units; attachments and no-pending abstain. Requested action selects facility 2, referral type selects note date 1, plan selects clinician 3. Manual correction would largely require clearing and rebuilding the selections, not merely adjusting one or two fields.

Scoring is deliberately unchanged. Some exact mismatches are not inherently indefensible: date unit 1 may be relevant context for time-only observations, unit 18 may reasonably accompany an initial examination, unit 22 may be considered either a treatment follow-up or a later observation, and referral unit 29 already includes a reason while 28 supplies resource context. A clinician must adjudicate these boundaries and ambiguous date associations. Such context extras must not be equated automatically with clinical errors. Conversely, moving “tests not performed” into pending results, omitting explicit allergy absence, or attaching facility text to a requested clinical action cannot be explained by harmless boundary differences. No labels were relaxed after seeing results.

The earlier bilingual `source-id-v06-2` run remains an explicit **incomplete_output** at 72.773 s in its [original report](../evaluation/dev002-v06/results/comparison-20261004T071448Z.json). It was not rerun, repaired, counted as abstention or omitted from the project record. Its missing runtime termination metadata remains a limitation; the new runner now retains raw envelopes even on validation failures.

## Additional existing development cases

The five existing lowercase `dev-001`–`dev-005` cases are separate fictional families from uppercase clinician DEV-002. Only their development notes were used; original fixtures and historical schema/results were not overwritten. New experiment snapshots record their original schema and the v0.6 contract being tested. No held-out cases were read or used, and no new clinical cases or reviewed labels were created.

All 15 additional candidate/case results were structurally valid. They have **no v0.6 expected assignments**, so numeric missing/extra scoring is unavailable, not zero. The following is a qualitative source-text audit, not adjudicated clinical evaluation. Raw outputs and every abstention remain in [baseline 1.7B](../evaluation/recovery-v06/baseline-1.7b-other/report.json), [baseline 4B](../evaluation/recovery-v06/baseline-4b-other/report.json), and [grouped 1.7B](../evaluation/recovery-v06/grouped-1.7b/report.json).

| Case | Baseline 1.7B total | 4B total | Grouped 1.7B total | Observed failure / clinician work still needed |
|---|---:|---:|---:|---|
| dev-001: cough/negatives | 8.782 s | 19.004 s | 20.645 s | Baseline 1.7B complaint omits cough/fever negative, diagnosis points at no tests. 4B puts allergy absence under regular medicine and abstains on allergy. Grouped duplicates all units into initial/current observations, invents pain-change sources and attachments. Restore actual complaint/negatives and distinguish a patient-reported dose from verified in-visit administration. |
| dev-002: sparse/unknown | 6.410 s | 15.549 s | 14.983 s | Baseline 1.7B puts headache into examination, leaves unknown allergy empty. 4B assigns missing vitals to referral and unknown allergy to requested action. Grouped assigns “diagnosis not written” to allergy and headache to referral type. Explicit missing/unknown statements need correct placement; unsupported fields should stay empty. |
| dev-003: explicit negatives | 7.389 s | 14.514 s | 20.508 s | Baseline 1.7B loses allergy/no-treatment/no-test negatives; 4B abstains on all 19 fields despite explicit statements. Grouped puts all units into referral/action/plan and omits allergy/no-treatment. Restore documented negatives without inventing findings or referral decisions. |
| dev-004: medication chronology | 8.510 s | 20.882 s | 18.306 s | Both single-call models put a prior amoxicillin course under regular and administered medication; baseline 1.7B allergy selects today's paracetamol. Grouped allergy selects prior antibiotic rather than rash, treatment includes prior course/rash, glucose is labeled attached. Distinguish historical course, reported dose, actual administration and allergy; no later/current assessment is documented. |
| dev-005: contradictory history | 9.779 s | 18.493 s | 22.682 s | Baseline 1.7B allergy selects suspected pneumonia, diagnosis loses later “not confirmed,” and current temperature abstains. 4B preserves morning/evening temperatures but loses both allergy statements and assessment uncertainty, and calls assessment changes pain change. Grouped allergy selects suspected pneumonia; current includes morning/evening temperatures, and requested action selects rash rather than the request to clarify contradictions. Retain both conflicting allergy/assessment statements and temporal distinctions. |

All new calls used the same deterministic runtime settings and no other inference calls were launched by these runners concurrently. CLI experiments do not share the application's queue; this is not a concurrent-user or repeated-run performance benchmark. The live web/Ollama services were not restarted.

## Printing and review burden

The same [normally completed fictional fixture](../evaluation/recovery-v06/normal-print-fixture.json) was entered through the UI, with **no inference**. Clinical values were transcribed from the source/provisional mapping strictly for layout testing. The exact source note remained unchanged. Time-only examination/treatment values remain time-only; the note date is not silently attached. No later clinician-added clinical facts or signature were fabricated. Browser approval checkboxes are simulated QA actions, not clinician approval of DEV-002.

Observed in installed Chrome 154:

- Previous renderer: **7 pages** for this normally completed fixture. New renderer: **2 pages**, A4 with 11-point body text; no hard page cap or text truncation.
- Long-text stress fixture is separate: **3 pages**, all 35 long-text lines and three intact treatment rows retained. The older seven-page stress result remains preserved.
- Original source suggestions, separate source-ID buttons, original-extraction excerpts and newly proposed evidence stay in the review interface. They are no longer repeated in each exported field. Original `[Sxx]` markers already embedded in an unedited narrative remain verbatim; there is no silent clinical-text rewriting. Export includes actual form values, explicit negative/uncertain meaning where recorded, relevant unresolved-information notes, and unfilled signature/reviewer fields.
- Doctor-entered/edited values have `*` and one explicit attribution legend stating that extraction evidence does not verify the edited content. It is not copied repeatedly beside every field. Pending/treatment/oxygen/transport selections that carry clinical meaning remain visible; a purely procedural investigation-review selection is represented by its unresolved warning only when applicable. Conflicting explicit no-treatment versus treatment rows is not hidden.
- Empty optional slots no longer consume a heading, placeholder and repeated explanation each; core missing-information warnings still print. The print instructions explicitly tell the doctor that source suggestions do not export and needed content belongs in the clinical fields/treatment rows. The normal fixture retains no-other-treatment, unasked-dose, not-assessed range of motion, test-not-performed and no-pending facts.

The obvious duplication removed here is **export duplication**, not clinical review: source suggestions plus manually transcribed detail, original excerpts plus edited text, per-field boilerplate, and blank optional entries. The UI still requires manual transcription of detailed observations/treatment; unreliable broad extraction cannot safely remove that work. Conditional pending/oxygen/treatment review, source-change reconciliation, case-replacement confirmation and both approval acknowledgements remain. No semantic confirmations are inferred from nonempty text. A potential future reduction in typing is explicit doctor-selected source insertion for a chosen field with provenance; it is not implemented or claimed validated here.

Both normal pages and all three stress pages were visually inspected for readable Mongolian text, clipping, headers, footers and row continuity. [Print-check metadata](../evaluation/recovery-v06/print-check.json) records PDF hashes and counts; PDFs/PNGs remain ignored in `.runtime/recovery-print` and `.runtime/recovery-stress`. No browser/printer universality is claimed.

## Reproduction and verification

Use the existing environment; these commands download nothing. Model experiments save into **new** directories and refuse to overwrite an existing result directory. Only bundled fictional development notes are accepted by these entry points.

```sh
# Single-call contract, all six development cases, alternate fresh destinations:
.venv/bin/python -m scripts.recovery --model qwen3:4b --output .runtime/recovery-new-4b
# One fixed five-group design, same notes:
.venv/bin/python -m scripts.recovery --model qwen3:1.7b --grouped --output .runtime/recovery-new-grouped
# Recompute summaries from saved artifacts; no inference:
.venv/bin/python -m scripts.recovery_summary
.venv/bin/python -m pytest -q tests
node --test tests/*.test.mjs
# Set PLAYWRIGHT_MODULE and CHROME_EXECUTABLE to existing installations:
node scripts/verify_recovery_print.cjs
UI_OUTPUT=.runtime/recovery-stress node scripts/verify_v06_ui.cjs
# In an existing environment containing pypdf:
python scripts/check_recovery_pdf.py
```

The initial actual-adapter 4B capture is reproducible with `PYTHONPATH=. .venv/bin/python experiments/recovery-v06/capture_initial_4b.py` in a fresh checkout without its output file; it refuses to overwrite the preserved capture. For routine comparisons use the parameterized runner above. Runtime contract-equivalence and original evidence-offset integrity are covered by tests.

Observed checks: **75 Python tests and 24 JavaScript tests passed**, plus both real-browser workflow runners and the normal/stress PDF checks. An initial bare `.venv/bin/pytest -q` invocation encountered a repository-import collection error in `scripts/offline_test.py`; both `.venv/bin/python -m pytest -q tests` and the documented full `.venv/bin/python -m pytest -q` invocation pass. No application code change was needed for that invocation issue. Browser checks use mocked provisional assignments only to isolate workflow safety, and manual fixture data for normal printing; real model calls are separately captured above.

Tests cover group completeness/strict failure, unchanged offsets/source text, baseline request equivalence, separate missing/extra counts, explicit abstentions, source-suggestion exclusion from print, preserved manual attribution, no original/new evidence leakage, uncertainty and treatment conflicts. Existing case-reset, late-response, reconciliation and approval tests still pass. The live application remains healthy and model-ready; readiness only checks runtime/local-model availability, not extraction quality or offline operation.

## Recommendation and unresolved work

**Recommendation:** retain the editable v0.6 form and clinician review, use manual source selection/transcription as the reliable preparation route, and narrow any future AI role to optional source-location suggestions for **one clinician-selected field at a time**, with no automatic category population or synthesized clinical prose. That narrower AI interaction still needs a bounded test; this milestone does not establish it works.

The two new candidates are not usable replacements for broad extraction on these cases; changing defaults would not be justified. The model-facing numbering cleanup is useful experimental instrumentation, but did not recover performance and is **not enabled in serving**. No reviewed-label score, clinical accuracy improvement, held-out generalization, offline success, training result or hosted performance is claimed.

Remaining blockers: clinician-reviewed final schema and labels/boundary policy; truthful handling of negation, temporal states and medication roles; a compatible comparator for supported non-thinking use if later authorized; and an independently reviewed evaluation set. A single good field or valid JSON is insufficient. Keep the current baseline/tag for reproducibility and rollback. Do not start training to compensate for an unaudited input/label contract.

Measured work interval through final verification: **14.7 minutes**, 07:28:53–07:43:33 UTC, inside the requested 45–60 minute ceiling. There were **41 new inference calls across 17 candidate/case runs**, plus reuse of one preserved baseline case. Investigation stopped after the one chosen simplification; no further prompt search was performed. Commit/push follows this verification interval. See [verification.json](../evaluation/recovery-v06/verification.json).
