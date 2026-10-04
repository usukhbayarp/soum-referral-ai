# Fictional development evaluation — 2026-10-04

**UNREVIEWED. No clinical accuracy, sensitivity, safety or clinician-approval claims.** Five AI-authored fictional notes are deliberately limited to development mechanics; no held-out test cases exist yet. Clinical labels are null and must be supplied by a clinician. The scoring CSV is blank in all clinician-score columns.

## Measured setup

Apple M4, 10 CPU/10 GPU cores, 16 GiB unified memory, macOS 15.1; Ollama 0.34.0. A single sequential pass per model/prompt over exactly the same five fixture notes. Models unloaded after each request and before the next model. Latency is wall-clock including load, prompt evaluation, generation and validation; it is not a statistically stable benchmark. Machine had other applications running. No training was performed.

Settings: `think:false`, JSON schema `format`, `stream:false`, temperature 0, seed 42, context 16,384, output 1,600 tokens, `keep_alive:0`. Schema provisional-0.1; output source-id-1; segmentation sentence-lines-1. Exact fixture/config hashes, raw outputs, resolved evidence, abstentions, errors, runtime version, model details and timings are in timestamped JSON files. The second run additionally records runtime templates and hashes. Initial prompt 1 outputs are preserved unchanged; one bilingual revision produced prompt 2. No further prompt tuning was done.

| Prompt | Model | Structurally valid cases | Empty field arrays | Latency range (s) | Mean (s) |
|---|---|---:|---:|---:|---:|
| source-id-1 | qwen3:1.7b | 5/5 | 11/35 | 2.53–7.82 | 4.47 |
| source-id-1 | qwen3:4b | 5/5 | 35/35 | 4.50–5.86 | 5.09 |
| source-id-2 | qwen3:1.7b | 5/5 | 11/35 | 3.97–6.10 | 4.72 |
| source-id-2 | qwen3:4b | 5/5 | 7/35 | 8.87–11.82 | 10.02 |

“Structurally valid” means all assigned IDs exist and the response matches the schema, **not** that selected text belongs in that field. Empty arrays are model abstentions, not proof that information is absent. Every failure and abstention is retained. There were no invalid responses or runtime failures in these 20 measured calls; failure handling is covered separately with mocks.

## Exact local artifacts

- `qwen3:1.7b`: digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`; 1,359,293,444 bytes; Q4_K_M. GGUF general.size_label is 1.7B, parameter_count is 2,031,739,904 and runtime summary says 2.0B. Downloaded through the existing Ollama installation; digest verification succeeded.
- Cached `qwen3:4b`: digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`; 2,497,293,931 bytes; Q4_K_M. Metadata identifies **Qwen3-4B-Thinking-2507**, not the standard hybrid-thinking 4B assumption. It loaded successfully; no previous-project configuration is needed to explain a load failure. Its template opens a thinking block. The API accepted `think:false` and returned no separate thinking content, but true non-thinking semantics of this variant are unverified.

## Direct observations for clinician review (not scores)

- Prompt 1, 4B: all 35 field arrays were empty. They were retained as abstentions.
- Prompt 1, 1.7B: the ordinary case omitted the explicit diagnosis and allergy sentence. The missing-information case assigned a headache sentence to diagnosis/referral. Exact source text did not prevent wrong categorization.
- Prompt 2, 1.7B, ordinary case: selected both symptom units and each explicitly labeled examination, investigation, diagnosis, medication, allergy and referral unit. This is an observed ID pattern, not a clinical assessment.
- Prompt 2, 1.7B, negation case: selected the absent-allergy and no-treatment sentences under investigations, left their intended categories empty, and grouped an examination negative under history.
- Prompt 2, 1.7B, medication case: placed the previous amoxicillin medication sentence in diagnosis and allergies. The actual allergy statement was not selected under allergies.
- Prompt 2, 4B: produced nonempty output but omitted the ordinary-case “Халуураагүй.” from history. In the missing-information case it placed unknown-allergy text under investigations. Other category errors remain.
- Prompt 2, temporal case: both models selected the earlier “no allergy” statement while missing the later rash statement from allergies. Therefore **no claim of general contradiction detection or complete temporal extraction is supported**. The whole source remains visible for correction.

## Milestone decision

Keep `qwen3:1.7b` as the configurable default for the **fictional mechanics demonstration**, because it is smaller, has the expected hybrid template/non-thinking switch, and was faster in this small second pass. This is not a clinical-quality selection. Preserve cached 4B unchanged. Narrow scope to source-unit proposals plus mandatory manual review; do not broaden to generated summaries, recommendations, or autonomous referral decisions. Review every field and compare it against the entire note. A clinician must correct errors before any useful quality assessment or demonstration claim.

## Scoring and next evaluation

`clinician-scoring.csv` includes a row per model/prompt/case/field, selected IDs, and blank review columns. Reviewers should provide expected ID sets, note missing/wrong categories, check negatives/uncertainty/numbers/units/dates and temporal context, and document corrections. Do not fill scores from schema validity. After review, add canonical expected assignments and review status to a new reviewed dataset; preserve original unreviewed fixtures/results. Use case-grouped held-out data for final evaluation only.

Run `python -m scripts.compare --models qwen3:1.7b soum-tuned:latest` in the project environment to compare a future local candidate on the identical current development contract/settings. Use `EXTRACTION_PROMPT_VERSION=source-id-1` to reproduce the earlier prompt. Export utility excludes all current fixtures from training because they are unreviewed. Model updates require digest comparison; tag names alone do not pin weights.
