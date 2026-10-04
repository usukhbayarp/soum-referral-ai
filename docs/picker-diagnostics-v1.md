# Bounded treatment-picker diagnosis — 2026-10-04

**Decision D: keep the AI picker disabled.** Neither tested configuration adds demonstrated value to this narrow treatment-selection workflow. Use the corrected manual v0.8 form; no model or prompt is promoted.

This report covers fictional development mechanics and scoped label agreement, **not clinical validation**. The application, legacy extractor, prompts, schemas, model tags, historical results and default-disabled picker are preserved. No training, final-test contents, paid hosting, submission or live restart.

## Audit: observations versus hypotheses

**Observed:** started from clean main `cf44475a11e62bd9091f84270c080fbaa657733f`. Ollama 0.34.0. The evaluated control is `soum-qwen3-4b-control:mlx128-52a5ab34`, digest `a7949c7fd19f24caf6f062c16c5733fa72c5c8049a53ec34681ccc426b6eb5f6`, 4.0B Q4_K_M, derived from `Qwen/Qwen3-4B-MLX-4bit@52a5ab34fa604bc8af6d3ce0cac0cab10b7eb495`. This is the conversion-matched untuned original-Qwen3 control, neither the separate official GGUF nor cached Thinking-2507 `qwen3:4b`. Prior provenance and failed medfacts pilot were inspected; export/training verification was not repeated.

The actual `/api/chat` UTF-8 bodies and raw responses are saved per attempt. A separate `_debug_render_only` request returned the **actual runtime-rendered control prompt without generating tokens**: one system turn, one user turn, one assistant prefix; system has the previously documented extra blank line; user ends in `/no_think`; assistant has one empty `<think>\n\n</think>` block. No nested/duplicated chat templates. GGUF adds neither BOS nor EOS automatically, and EOS 151645 is `<|im_end|>`, matching the pinned tokenizer. System precedes source text. No extra model system/messages are configured. Control GGUF advertises 65536 context (a known source-metadata difference); requests use 16384. This does not verify maximum-context behavior.

These controls are supported by the [Qwen original model card](https://huggingface.co/Qwen/Qwen3-4B) and installed-release [Ollama request types](https://github.com/ollama/ollama/blob/v0.34.0/api/types.go), [rendering code](https://github.com/ollama/ollama/blob/v0.34.0/server/prompt.go) and [chat route](https://github.com/ollama/ollama/blob/v0.34.0/server/routes.go). Temperature 0, seed 42, output cap 512, `think=false`, `keep_alive=0` remain fixed. Qwen's suggested non-thinking sampling differs; this is not evidence that deterministic extraction is broken. No returned thinking text was observed. The server's internal model token stream was not instrumented.

**Observed:** current request builder equals all three historical captured requests exactly. Integer IDs resolve to exact original text/Unicode offsets. Original `[Snn]` markers are stripped only at the start of model-facing unit text; offsets and original note are preserved. No offsets or competing S IDs are sent. The schema has one `ids` array, integer enum of legal IDs, uniqueness and max 80; no descriptions, placeholder answer, minimum-selection requirement or instruction to select every option. The application rejects duplicate keys, booleans/nonintegers, duplicate/unknown IDs and incomplete responses. There is no reference-answer repair. Direct diagnostics use this same resolver. No demonstrated discrepancy between application request/lookup and runtime response explains the failures.

**Hypotheses, not defects:** comprehension of Mongolian instructions, instruction/input-copying tendencies, task difficulty and effects of the converted/quantized control remain possible. This experiment does not isolate conversion against original full-precision weights. The short-input failures cannot be explained solely by long-note context. No application defect or justified runtime fix was found.

## Frozen comparison

[Plan and raw artifacts](../evaluation/picker-diagnostics-v1/) were written before inference. Three snippets use only reviewed original units: medication roles (DEV-002 U11/U12/U21/U23, expected 21/23); unrelated negatives (dev-003 U1/U2/U5/U6, expected 6); treatment mixed with examination/investigation (dev-003 U4/U6/U7, expected 6). These are **two correlated development families**, not three independent patients. Original text, offsets, IDs and family/split are retained. No facts were invented, and no development family was moved into training/test.

A: original Mongolian units, unchanged `treatment-picker-1` instruction, ID schema. B: only source text translated to English; same IDs and **same Mongolian instruction**, isolating source-language change but not testing an entirely English task. Translations are engineering diagnostics, not clinician-approved translations. C: original Mongolian text without IDs plus a simple Mongolian question, no system message or output schema. C changes several aspects, so any improvement would not isolate JSON alone. Direct answers must preserve given versus not given/OTHER treatment, dosage/route/time when provided, and exclude unrelated negatives; the rubric was frozen first.

A/B use `treatment-picker-1`; C uses `direct-question-1`; diagnostic plan version `picker-diagnostics-1`. All attempts stay in denominators. Schema validity is separate from semantic correctness. Retrieved/missing/extra/unreviewed selections and abstentions are separate. Invalid output receives no retrieval credit, with positive labels retained as unscorable. Exact selection remains reported.

After the control's first nine calls, one schema hypothesis was frozen: remove **only** top-level `format` from the three A requests. Same JSON instruction, model, source, settings and parser. The control instead copied input `units` objects with an extra closing brace on all three. This does not support disabling the schema as a repair; it also does not prove schema constraints have no effect.

## The sole tested alternative and acquisition deviation

**Observed identity:** cached `llama3.1:8b`, Meta `Llama-3.1-8B-Instruct`, digest `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`, 8,030,261,312 parameters, Q4_K_M, 4,920,753,328 bytes on disk. No new Llama download. Its [publisher card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) documents an instruction-tuned multilingual model with eight supported languages; Mongolian is **not** among them. This provides a distinct instruction-following baseline, not a Mongolian proficiency claim. It uses the Llama 3.1 Community License, compatible with this bounded local fictional experiment subject to its terms; redistribution has separate obligations. Its native Ollama template and metadata identify Instruct, system/user/assistant headers, BOS 128000 and end-of-turn/EOS 128009. A render-only probe verified those boundaries, with no Qwen markers or thinking controls. The Ollama distribution digest is the serving pin; an exact upstream HF weight commit is not exposed by this cached package.

**Why the selection changed before inference:** initially selected Google Gemma 3 4B IT/Q4_K_M for its [documented 140+ language training](https://ai.google.dev/gemma/docs/core/model_card_3), [supported Ollama package](https://ollama.com/library/gemma3:4b-it-q4_K_M) and [Gemma terms](https://ai.google.dev/gemma/terms). Its one authorized new-model download failed to make durable progress: the API counter reached 1,036,861,376/3,338,792,448 bytes, then fell to 93,856; a single resume also rolled back. After roughly 24 minutes across the pull attempts, stopped only owned HTTP clients, preserving **865,685,184 bytes of resumable partial progress** and the partial cache (preallocated file size 3,338,792,448 bytes; incomplete and not checksum-verified). No service restart, cache deletion or second-model download. Exact network cause is unverified; [Ollama v0.34.0 download code](https://github.com/ollama/ollama/blob/v0.34.0/server/download.go) confirms progress can roll back on transfer errors. This was an acquisition blocker, not a Gemma quality result.

**Gemma received zero inference calls.** Its frozen but unexecuted plans remain preserved. `candidate-llama-plan.json` records the explicit fallback decision before candidate inference. Llama is the **only alternative evaluated**, with the same nine tasks/settings/labels, supported native template, and no Qwen `think` parameter. This prioritizes the already available model and a concrete stopping decision over further download troubleshooting. No claim is made that Gemma would fail or succeed. Its native-message preparation is retained solely as an abandoned pre-inference artifact.

## Results and interpretation

**21 generation requests total:** control 9, schema hypothesis 3, cached alternative 9. Two additional render-only requests generated no tokens (23 `/api/chat` calls even if those probes are counted). No retries or reference-answer repair. **Zero full-note requests**: the predeclared gate required 3/3 exact candidate Mongolian selections; actual result was 0/3. All 21 responses completed normally; zero timeout, truncation, returned thinking, empty answer or valid empty selection. Three unconstrained responses were invalid JSON/contract and remain failures.

| Model / condition | Structurally valid | Exact selection / semantic answer | Retrieved / reviewed positive occurrences | Missing | Reviewed extra | Unscorable positive | All-call latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen control A: MN IDs | 3/3 | 0/3 exact | 4/4 | 0 | 6 | 0 | 17.40 s |
| Qwen control B: EN source, MN instruction | 3/3 | 0/3 exact | 4/4 | 0 | 7 | 0 | 14.19 s |
| Qwen control C: MN direct answer | N/A | 1/3 correct | N/A | N/A | N/A | N/A | 14.88 s |
| Qwen hypothesis: A without format | 0/3 | 0/3 exact | 0/4 credited | N/A | N/A | 4 | 48.12 s |
| Llama A: MN IDs | 3/3 | 0/3 exact | 4/4 | 0 | 6 | 0 | 29.28 s |
| Llama B: EN source, MN instruction | 3/3 | 0/3 exact | 3/4 | 1 | 6 | 0 | 26.93 s |
| Llama C: MN direct answer | N/A | 2/3 correct | N/A | N/A | N/A | N/A | 20.41 s |

Counts are **occurrences across snippets**, not independent clinical facts or patients. U6 recurs in two correlated dev-003 snippets. All selected snippet units have reviewed scope; unreviewed selections = 0. Invalid rows have unscorable, not zero-error, outcomes. `comparison.json` and each raw run retain token counts, exact selected/missing/extra IDs and latencies.

Representative failures and manual correction burden:

- Both A models select `[11,21,23]` for medication roles: remove regular amlodipine U11, retain administered paracetamol U21 and no **other** treatment U23. Qwen B also incorrectly adds the not-asked dose U12; Llama B omits U23. Not-asked cannot be treated as not-taken/not-administered.
- Both A models select all units in the other snippets: `[1,2,5,6]` and `[4,6,7]`. Remove cough/fever/allergy negatives and examination/investigation findings; retain only no-treatment U6. Literal negation is preserved by exact source retrieval, but its category is wrong.
- Qwen's direct medication answer says **Энэ үзлэгээр эмчилгээ хийгээгүй.** (“No treatment during this encounter”), contradicting the given paracetamol. Llama says only **Эмчилгээ.** (“Treatment”), omitting all relevant facts. Both require the doctor to reconstruct the treatment description from the original note.
- Qwen's other direct answer repeats a malformed exclusion instruction; only its investigation-mixed snippet gives the correct no-treatment answer. Llama correctly answers both no-treatment snippets, which share the same underlying family; this is not independent generalization evidence.

**Interpretation:** English source text did not improve exact selection under the fixed Mongolian instruction. This does not test an all-English instruction or prove a universal language limitation. Direct-answer results show some no-treatment comprehension, but neither model handles the clinically important medication-role snippet. Schema removal harms structural validity without demonstrating semantic recovery. Input-copying/instruction-following failure is observed; its underlying language/model/quantization cause is not isolated. Both models fail short inputs, so length alone is insufficient to explain prior full-note failures. Llama retrieves no more Mongolian positives and has the same irrelevant selections, at greater latency. There is no supported targeted application fix or basis to promote either model.

## Runtime resources and focused verification

Measured sum of nine request wall times: **Qwen 46.46 s; Llama 76.62 s**. All 21 generation calls sum to **171.20 s**, including model loading and response transfer; acquisition, artifact writing and unload-poll overhead are separate. Every call used `keep_alive=0` and the next generation waited for an empty `/api/ps`, so these are sequential cold-load application-style measurements, not best warm-token throughput. Inputs were 211–520 prompt tokens, outputs 8–160 tokens, well below 16384 context and 512 output limits; no truncation observed.

Observed peak Ollama-reported model allocation/residency: control **5,106,921,635 bytes (4.76 GiB)**, Llama **6,893,170,851 bytes (6.42 GiB)**, reported GPU allocation equal to those values. These are neither total process RSS nor total system use; do not add overlapping memory measures. System pressure levels 1/2/4 occurred: one critical sample among 83 control samples, three among 139 Llama samples. Both completed on the 16-GiB M4, but that does not establish comfortable resource headroom or acceptable performance on every machine. No shared process was killed to free memory.

Focused offline tests cover strict scoring, invalid-output exclusion, source/offset/review provenance, paired-language variable isolation, and native-message/control differences. Application code did not change, so broad application/model evaluation was not rerun. **11 focused tests passed in 0.19 s** (`.venv/bin/pytest -q tests/test_picker_diagnostics.py`); final runtime observations are recorded in `verification.json`. No clinical quality is inferred from software-test success.

**Next action D:** retain the off-by-default picker and use the corrected manual form after the existing live draft is resolved. Stop this local model/task iteration at the documented result; no generic preparation cycle, training proposal or successful-AI claim follows these diagnostics.

## Delivery and live application

The live process remains PID 69834 at **http://127.0.0.1:8000**, `experimental-0.7`, baseline `qwen3:1.7b`. The isolated preview remains PID 85109 at **http://127.0.0.1:8001**, `experimental-0.8 / clinician-placement-picker-3`. Its picker remains explicitly enabled for review only as before; the code default remains **off**. No process was stopped and no existing browser tab/draft was operated on. Saved `/api/config` observations are included.

After the user finishes/exports or deliberately discards the existing live draft, the safe manual-form activation command remains:

```sh
cd /Users/usukhbayar.purevdorj/Documents/hackathon
if [ "$(lsof -nP -iTCP:8000 -sTCP:LISTEN -t)" = "69834" ]; then
  kill -TERM 69834
  while kill -0 69834 2>/dev/null; do sleep 1; done
  TREATMENT_PICKER_ENABLED=0 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
else
  echo 'Live process changed; inspect before restarting.'
fi
```

This command was **not executed**. It changes the serving process, not the existing draft's storage; resolve the draft before running it and reloading. The preview can be used without restarting live.

Outstanding delivery remains: clinician workflow review and final form/labels; explicit disconnected/offline acceptance testing; any separately chosen hosting/provider/budget and hosted acceptance; held-out final evaluation and submission. None is represented as complete here.
