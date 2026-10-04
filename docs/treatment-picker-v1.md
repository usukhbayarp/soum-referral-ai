# Treatment source-picker review milestone — 2026-10-04

**Decision: keep disabled by default.** The review workflow works mechanically, but the one bounded model experiment missed administered paracetamol and over-selected irrelevant passages. It has not demonstrated clinical usefulness or saved clinician time. No training, model promotion, cloud deployment, final-test access or submission occurred. Historical medfacts and A-v2 artifacts remain unchanged.

## Doctor-facing placement

Form `experimental-0.8`, revision `clinician-placement-picker-3`, implements the placement decisions supplied by **А. Балжинням, 2026-10-04**:

- Manual **Гэрээр хэрэглэсэн эм тариа** is nested inside **Одоогийн өвчний түүх**, not a new main section. Only documented home/pre-encounter use related to the current complaint belongs there. The app does not infer this relationship or copy regular medication into it.
- **Тогтмол хэрэглэдэг эм** appears once, retaining documented current dose/time and patient attribution. Home use alone does not move it elsewhere. Free-text correctness and avoidance of manual semantic duplication still require doctor review.
- **Хийсэн эмчилгээ, ажилбар — хүүрнэл** holds encounter treatment/procedure narrative and explicit non-administration together. Negatives never automatically become medication rows. Planned actions are not described as performed. A wound-washing solution is not converted into IV administration.
- The corrected legacy past-history proposal remains separate from both manual current/chronic history. No chronic diagnosis is inferred from a medication.

This supersedes the older not-given/current-illness placement instruction for the current form. Historical instructions and training targets are preserved as historical records. TRAIN-003 was **not reconstructed, added to a dataset or marked fully reviewed**. Its supplied placement example is only guidance: retain patient-reported losartan 50 mg at 07:10 in the regular entry once; injury-related home medication is undocumented, not absent; saline wound washing is a procedure. No new source facts were inferred.

## New experimental contract

`experiments/treatment-picker-v1/{prompt.txt,contract.json}` freezes **treatment-picker-1**. Model: **soum-qwen3-4b-control:mlx128-52a5ab34**, digest **a7949c7fd19f24caf6f062c16c5733fa72c5c8049a53ec34681ccc426b6eb5f6**. No adapter model is used. The small output is only `{"ids":[23]}` or `{"ids":[]}`; there are no generated quotations, clinical values or attribute objects. The old placeholder-quotation/all-attribute failure is avoided by changing the task, without editing the previous experiment.

Existing `sentence-lines-1` integer IDs and original Unicode codepoint offsets are reused. Only original leading `[Snn]` markers are stripped in the model-facing presentation to avoid two ID namespaces; original note bytes/text/offsets remain unchanged. The application validates JSON keys, integer type, duplicate/unknown IDs and runtime completion, then retrieves exact original passages. It also shows previous/next units and the complete original S paragraph separately as context. Context is not automatically inserted, nor scored as a selected passage. Full-note access remains visible. Distant date context is not automatically associated with a time-only passage.

Temperature 0, seed 42, context 16384, output limit 512, think=false, keep_alive=0, timeout 120 seconds. Model identity is checked against the pinned local GGUF digest. The API shares the existing bounded inference gate, loopback restriction, origin/body limits and no-content-logging policy. Manual entry remains available on failure.

`TREATMENT_PICKER_ENABLED=0` is the default; the endpoint rejects requests when disabled. It is independent of the legacy broad extractor and never changes its production model/prompt. The UI labels the broad extractor separately and does not claim its quality problems are fixed.

## Frozen development experiment

The pre-inference plan is `evaluation/treatment-picker-v1/plan.json`, derived only from existing partial clinician annotations. One request each for DEV-002, dev-003, dev-004: **three requests total**, no retries or prompt sweep. Expected reviewed positives: DEV-002 IDs **21,23**; dev-003 ID **6**. Reviewed negatives use the corresponding approved categories. dev-004 has only reviewed measurement/investigation negatives, **no reviewed treatment positives**; its original ambiguous medication statements were not relabelled using the later home-use clarification. No held-out contents were opened.

| Input | Selected IDs | Reviewed positives retrieved / known | Missed reviewed positives | Reviewed irrelevant selections | Unreviewed selections | Request latency |
|---|---|---|---|---|---|---:|
| DEV-002 | 23 | 1/2 | 21 | none | none | 8.87 s |
| dev-003 | 1–7 | 1/1 | none | 1,2,3,4,5,7 | none | 4.44 s |
| dev-004 | 1–5 | no supported positive denominator | not assessable beyond reviewed scope | 3,4 | 1,2,5 | 4.47 s |

All **3/3** outputs satisfy the ID/evidence contract; **zero empty/invalid/timed-out/truncated outputs**. This is not semantic success. Across the reviewed scope: **2 of 3 relevant units retrieved, 1 missed, 8 reviewed irrelevant selections, 3 unreviewed selections**. Total latency **17.78 s**. Prompt/output tokens respectively: DEV-002 **1702/7**, dev-003 **500/18**, dev-004 **567/14**. This denominator is a new narrow retrieval task; no numeric superiority claim over medfacts or A-v2 is valid.

Exact examples shown to the doctor:

- DEV-002: **Энэ үзлэгээр өөр эмчилгээ хийгээгүй.** Its neighboring units and entire original S06 paragraph (including administration ID 21) are visible separately as context. ID 21 is still a missed model selection, not credited as retrieved. The word **өөр** remains: this is not a claim that all treatment was absent. The picker omitted ID 21, documenting paracetamol 500 mg orally once at 10:15. Timing and attribution within retrieved units are copied without alteration; omission remains a serious failure.
- dev-003: selects **Эмчилгээ хийгээгүй.**, but also **Ханиалгагүй.**, **Халуураагүй.**, **Амьсгаадаагүй.**, examination, allergy and investigation negatives. Their negation is preserved literally but their treatment relevance is wrong.
- dev-004: selects everything, including **Халуун 37.2 °C, АД 120/80 мм.муб, жин 62.5 кг.** and **Глюкоз 5.6 ммоль/л.**, which are reviewed as measurements/investigation. The unreviewed medication statements remain ambiguous; neither home use nor encounter administration is inferred. Its allergy passage is also an obvious engineering concern for this field, retained in the unreviewed bucket rather than assigned a new clinician label.

The raw requests/responses and initial adjacent-only context are preserved in `results.json`. `review-display.json` records the deterministic review presentation expanded to the whole original S paragraph plus neighbors, without new inference or altering the selected IDs/scores. The [clinician review sheet](../evaluation/treatment-picker-v1/clinician-review.md) includes original notes, exact suggestions, known errors and unanswered “Relevant?”, “Anything important missing?”, “Would accepting/correcting this save work?” questions. No acceptance or time savings were fabricated.

## Review workflow and verification

When enabled, suggestions are separate cards with exact source and expandable adjacent context. Accept inserts that unit's exact text into narrative, never medication rows. Reject leaves the form unchanged. Reaccepting the same unit or exact existing text is prevented. Manual edits retain accepted-source snapshots with an explicit statement that these do not verify edited content. Accepted/edited content invalidates approval and print content. Source changes retain manual work but require reconciliation; case reset clears it, and stale responses cannot populate a changed case/draft. Empty selection explicitly does not mean no treatment occurred.

**28 focused Python tests and 37 JavaScript tests passed**, plus isolated browser checks using captured responses (no additional inference). Checks covered invalid/duplicate/unknown IDs, exact negation/context, flag/API boundaries, accept/reject/duplicates, manual attribution, source reconciliation, reset/stale responses, history placement and regular-medication non-copying. One existing Starlette/AnyIO deprecation warning remains.

Normal fictional DEV-002 print: **2 pages**, both rendered and visually inspected for legibility, clipping and attribution. The new QA fixture manually places existing hypertension text in chronic history and the existing no-other-treatment statement in narrative, removing its duplicate from the prior fixture's medication response cell; historical fixture files are unchanged. This is layout/workflow QA, not a clinician-approved completed referral. Regular medication appears once; negative narrative does not generate a medication row. Source debug cards/review controls are not printed. Signature remains blank.

## Available preview and safe activation

The isolated preview is **http://127.0.0.1:8001**, PID **85109** at verification, one uvicorn worker, no access log, serving **experimental-0.8 / clinician-placement-picker-3**, with the picker **explicitly enabled for review only**:

```sh
TREATMENT_PICKER_ENABLED=1 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1 --no-access-log
```

The existing live process at **http://127.0.0.1:8000** remains **experimental-0.7**, PID **69834**, model `qwen3:1.7b`, prompt `source-id-v06-1`; it was not stopped/restarted. An already-open draft remains in that tab. New static files remain compatible with its old configuration and keep the picker hidden.

**The user action needed before replacing that process is to finish/export or deliberately discard its current draft.** To activate the corrected manual form afterward, keep the experimental picker off and run this exact guarded restart from the repository root (the guard refuses if the observed live PID has changed):

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

Then open/reload port 8000 only after the old draft is resolved. The isolated preview can be used now without replacing the live process. No automatic feature activation follows software-test success.

## Smallest next decision

Have the clinician try accept/reject/manual correction on the three preserved development outputs and answer the review-sheet questions. Given the omission and over-selection, retain the off-by-default flag; decide whether the review controls alone help or whether to use manual source selection instead. Do not start another training/infrastructure cycle or activate the picker based on JSON validity.

Remaining delivery tasks are separate: safe live-form activation, clinician workflow review, explicit offline/disconnected acceptance testing, any chosen hosting/provider/budget work, final-test preparation/evaluation and submission. This milestone does not establish clinical accuracy, offline success, hosted deployment or submission readiness.
