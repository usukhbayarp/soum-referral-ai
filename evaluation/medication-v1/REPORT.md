# Medication/allergy comparison — provisional result

**Recommendation: neither A nor B for serving integration.** The complete referral application and production defaults are unchanged. Fine-tuning and better local model selection remain options; this is not a permanent narrowing of the product.

**A** assigns one of eight medication/allergy roles to every source unit; code assembles verbatim groups with original offsets. **B** proposes medication name/role/dose/route/time/frequency, intact allergy/context statements, and exact linked evidence quotes. B's lexical checks cannot prove the correct drug–detail relationship.

The local model was `qwen3:1.7b`, Q4_K_M, Ollama 0.34.0, digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`. Settings: `think:false`, temperature 0, seed 42, context 16384, output ceiling 1600, `stream:false`, `keep_alive:"5m"`, 60-second request timeout. No cloud inference or model download occurred.

Four fictional development notes were used: existing DEV-002, dev-003, dev-004, and one minimal engineer/AI-authored mixed/planned/not-given diagnostic probe. **All are unreviewed.** [Common expected facts](expected-facts.json) were frozen before inference, separate from model input. No held-out data was read. One documented prompt revision per candidate clarified instructions in Mongolian; all original failures remain saved.

| Observation | A | B |
|---|---|---|
| Structure, including repeat | 9/9 valid | 9/9 valid |
| Evidence mechanics | Verbatim by construction; roles still wrong | 0/9 fully passed lexical/intact-evidence checks |
| Useful partial result | V1 located DEV-002 administered paracetamol; v2 located the historical course and several probe roles | Some correct dose/time fragments; v1 retained penicillin-rash wording, v2 retained DEV-002 patient-attributed allergy absence |
| Blocking failures | Regular/historical drugs called administered; negatives dropped into other; genuine mixed sentence forced into one role | Wrong roles and drug–frequency/time associations, invented details, omitted administered treatment, and rash changed to “no allergy” |
| Remaining manual work | Correct groups and transcribe all treatment rows | Review/correct every medication row and its associations/evidence; zero complete rows ready unchanged in this audit |

For the two explicitly administered paracetamol events, a provisional source review finds 6 of 8 dose/route/time/frequency value fragments retainable in v1, versus 3 of 8 in v2. The remaining slots need correction or are omitted. **This does not approve either row:** wrong roles, altered quotes and other defects remain. It is not compared with A's classification count as an equivalent accuracy metric. No clinician timing was collected; no time-saved estimate is given.

Cold A/DEV-002 took **24.412 s**: load 3.6072 s, prompt evaluation 4.7288 s, generation 16.0426 s. Cold B was not measured. Warm DEV-002 v1 repeats took **10.286 s (A)** and **15.701 s (B)**; both repeated their erroneous first output byte-for-byte. One repeat does not prove general determinism. V2 DEV-002 took **13.018 s (A)** and **13.091 s (B)**; other warm case times and all runtime durations are in [summary.json](summary.json). All 18 calls completed normally; none timed out or reached the output ceiling.

**Next step:** compare the frozen contracts on this baseline against an independently verified original `Qwen/Qwen3-4B` local artifact, in its [documented supported non-thinking mode](https://huggingface.co/Qwen/Qwen3-4B). The installed Thinking-2507 tag with `think:false` is not that comparator. No replacement was downloaded here. Capacity, prompt language, quantization and runtime effects have not been causally isolated.

The repeated role, negation, association and exact-copy errors are plausible fine-tuning targets, not proof training will work or fail. The reused MLX-LM tokenization path verified completion-only masking and full sequences of **609–4,081 tokens** without truncation. A requires unit-role labels; B requires more detailed association/span labels. Final schema and reviewed train/development labels must precede a versioned canonical exporter adaptation and tiny training-to-serving test. Case families and held-out tests must remain separated. Keep both original and conversion-matched untuned baselines; future tuned/control runs must share the same conversion pipeline and contract. No training or conversion ran.

**Checks:** 83 Python tests, 24 JavaScript tests, and the static review-sheet browser check passed. Production files, model tags and historical results were preserved. No clinical validation, deployment or offline-success claim is made.

[Clinician review sheet](clinician-review.html) · [Detailed error audit, timing table and training implications](../../docs/medication-representation-comparison.md) · [V1 raw capture](run-v1/report.json) · [V2 raw capture](run-v2/report.json) · [Token/mask checks](token-mask-audit.json)
