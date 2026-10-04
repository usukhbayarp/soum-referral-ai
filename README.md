# Soum Referral AI / Сум

A local Mongolian referral-documentation prototype for the World Bank Small AI for Development hackathon.

**Fictional data only. The clinician-designed v0.6 schema is experimental, not an approved Mongolian national referral form or a replacement for 13А.** No diagnoses, treatment recommendations, referral eligibility decisions, or urgency assessments are generated. The model proposes source-unit classifications; the doctor must correct them before export. Incorrect classifications and omissions have been observed. This is not clinically validated.

## Run locally

Tested on Apple M4, macOS 15.1, Python 3.12.12, Ollama 0.34.0. The existing Ollama installation was reused. No training stack is installed in the project.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
# Start the installed Ollama application, or run this if it is not already running:
# OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 ollama serve
ollama pull qwen3:1.7b
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open **http://127.0.0.1:8000**. On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Windows/Linux execution and performance have not been verified. Lock file includes development/test packages; `requirements.txt` has the four pinned direct runtime dependencies.

Use “DEV-002 зохиомол жишээ” to load a fictional, **unreviewed** example. Extract, inspect the original alongside fields, click evidence IDs, correct fields, acknowledge unresolved information, approve, then print/save PDF. Missing facts may stay missing. Each edit revokes approval. **New referral / Шинэ илгээх бичиг** starts another case and clears source, administrative details, manual edits, evidence, approval and print content. Loading the fictional example also starts a fresh referral; existing content requires replacement confirmation. Cancel keeps the current draft intact. Reset uses the same full-clear action; previously exported files remain separately. No secure erasure claim is made for browser/OS memory or swap.

## Architecture and extraction contract

`Browser → FastAPI → replaceable OllamaAdapter → loopback Ollama → source IDs → strict validation → source text → doctor review`.

- The browser holds its own draft in memory; the backend has no shared patient state, accounts or database. Shared state is only a concurrency gate and immutable configuration.
- `config/referral.v0.6.json`: active six-section clinician-designed form and manual subfields; clinician completeness rules live in `app/static/completeness.mjs`. Empty required fields are allowed after explicit acknowledgement; these rules have no clinical authority.
- `config/extraction.source-id-v06-1.txt`: active source-selection prompt. The v0.6 variant 2 returned incomplete output under the unchanged limits and is retained only as an experiment. Old prompts and v0.1 schemas remain historical.
- `config/output.source-id-v06-1.json`: active output JSON schema. Inference restricts integer IDs to each request's units; validation rejects wrong types, unknown/duplicate IDs, extra/missing/duplicate fields, malformed or incomplete output. A failure is never silently converted into an empty assignment.
- `app/core.py`: `sentence-lines-1` segmentation. Split on newlines or `. ! ?` followed by whitespace/end; trim boundary whitespace, keep original Unicode code-point offsets and exact text. Decimal points remain intact. This is deterministic, **not a clinical sentence parser**. Abbreviations can split unexpectedly. The browser handles offsets using Unicode code points too.
- A valid ID proves only that text exists. It does **not** establish correct categorization, completeness, truth, or absence of contradictions. No confidence percentages or general contradiction detector exist. Multiple excerpts are retained in source order, including incompatible statements when selected; the original note always remains available.
- UI statuses distinguish extracted/awaiting review, model did not find/review source, failed extraction/evidence, and doctor-entered/edited. Explicit negatives/unknown/not assessed remain verbatim when selected. Administrative fields are manual only.
- Original extraction evidence remains accessible after doctor edits, explicitly labeled as **not verification of the edited text**. Re-extraction preserves those original excerpts and displays new selections as a separate proposal, never as evidence supporting retained manual content. Print attribution for manual fields does not list source IDs as support.
- Editing the source is a **same-case edit**: manual values, including administrative details, survive every keystroke and receive a visible reconciliation flag. Approval is blocked until each retained nonempty manual value is explicitly reviewed using its reconciliation button; editing/re-extracting or checking the generic approval boxes cannot bypass this requirement. Another source change requires review again. Historical extraction snippets remain readable, but their highlight links are disabled after a source change to avoid linking to a different text version. Use **New referral** for a different patient/case. Case/revision/request tickets reject late success or failure responses from earlier cases.
- Approval is a browser workflow safeguard, not an authenticated signature or tamper-proof record. Print content is constructed only after approval; unapproved printing shows a blocker.

## Runtime configuration

`DEPLOYMENT_MODE=local` is the default and says inference runs on this computer. `DEPLOYMENT_MODE=hosted` explicitly tells users their submitted text is processed on the demo server. Invalid values fail startup. This changes disclosure only: it does not provision hosting, change the loopback inference restriction, or enable remote access. Operators must set `hosted` when the browser and inference server are on different machines.

```sh
REFERRAL_MODEL=qwen3:1.7b OLLAMA_BASE_URL=http://127.0.0.1:11434 INFERENCE_TIMEOUT=120 \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Set `REFERRAL_MODEL` to another **installed local GGUF Ollama model**, including a future tuned model. UI/schema/approval stay unchanged. No automatic pulls, cloud fallbacks, or model choice by request are allowed. Roll back by resetting the variable to `qwen3:1.7b`; keep that model installed. Comparison supports `--models` too.

Verified `/api/chat` settings: `think:false`, `stream:false`, schema object in `format`, temperature 0, seed 42, `num_ctx:16384`, `num_predict:1600`, `keep_alive:0`. Models unload after each call to reduce memory pressure. These are reproducibility settings, not a claim of optimal generation quality. Exact runtime, model digest, artifact bytes, quantization, templates, timings and contract hashes are recorded in evaluation results. Ollama's `1.7b` tag reports ~2.03 billion total parameters in GGUF metadata; do not confuse the tag/size label with an independently verified parameter count.

The cached `qwen3:4b` is actually **Qwen3-4B-Thinking-2507** per local GGUF metadata. It loaded, but its template differs from 1.7B and opens a thinking block. The API accepted `think:false` and returned no separate thinking text in measured runs; internal non-thinking semantics for this variant are unverified. Do not treat it as an interchangeable standard Qwen3-4B baseline.

## Privacy and limits

- Application code never stores/logs interactive notes or model outputs. No localStorage/sessionStorage, cookies, analytics, remote fonts, scripts, or UI assets. HTTP responses have `Cache-Control: no-store` and a restrictive CSP. Text uses DOM text nodes/textarea values, never HTML insertion.
- Model endpoint must be HTTP loopback; HTTP proxy environment variables are ignored by the client. Only installed local GGUF entries are accepted. Ollama was observed listening on `127.0.0.1:11434`.
- **One Uvicorn worker only:** one active inference, two waiting, 15-second queue wait, 120-second inference timeout by default. Per-process limits do not provide distributed hosting limits. A canceled browser request may run until the bounded inference timeout; it cannot overwrite a newer draft.
- Input: 3,000 Unicode characters, 80 units, 32 KiB HTTP body, 10-second body receive timeout, conservative 12,000-byte assembled-prompt budget. Oversize notes are rejected, not truncated. Output: 1,600 generated tokens, 64 KiB runtime envelope, 24 KiB model content; incomplete generation is rejected. The conservative prompt budget reserves room within the 16,384-token context; maximum-length behavior still needs device-specific evaluation.
- Manual fields over 6,000 characters remain visible but block approval with an explicit warning.
- The comparison CLI is an **explicit exception to non-persistence**: it writes only the bundled fictional development fixtures' outputs. Do not adapt it to real notes or commit private data.
- Browser extensions, system swap, print spooler and Ollama's own logging behavior are outside application control. Do not enable debug prompt logging. This milestone is for fictional data, not clinical deployment.

## Verification and evaluation

```sh
.venv/bin/python -m pytest -q
node --test tests/*.test.mjs
.venv/bin/python -m scripts.compare
.venv/bin/python -m scripts.compare --models qwen3:1.7b soum-tuned:latest
.venv/bin/python -m scripts.dataset evaluation/fixtures/development.json
```

The active defaults are `REFERRAL_SCHEMA_VERSION=experimental-0.6` and `EXTRACTION_PROMPT_VERSION=source-id-v06-1`. For historical CLI reproduction only, explicitly set `REFERRAL_SCHEMA_VERSION=provisional-0.1 EXTRACTION_PROMPT_VERSION=source-id-1` (or `source-id-2`). Do not serve the v0.6 UI with the historical schema; use its historical Git commit for full application rollback. Version-mismatched fixtures are rejected, not relabeled.

Run comparisons while interactive extraction is idle: they are sequential within the runner but do not share the web process's queue. Each model is unloaded before advancing. Results are timestamped and preserved, including failures and abstentions. The runner intentionally uses fixed development cases, never held-out tests.

Read [evaluation/report.md](evaluation/report.md), [docs/verification.md](docs/verification.md), [docs/clinician-review.md](docs/clinician-review.md), and [docs/training.md](docs/training.md). There are **zero reviewed labels** today. Valid JSON is not accuracy. The true network-disconnected restart demonstration remains pending; no network disconnection was performed.

## Hosting and next milestones

This is a localhost application, not a deployed service. [Container packaging](docs/deployment.md) is prepared: the web image builds, Compose validates, and an offline container imports the application. Web and Ollama share a network namespace to retain strict loopback-only inference; hosted disclosure and explicit allowed hosts are required. `/api/health` is liveness; `/api/ready` checks runtime/local-model availability without loading the model. These new endpoints require a deliberate app restart; the existing demo was left running.

The optional MLX environment, pinned base/tokenizer, untuned export-to-Ollama control and reviewed-data training skeleton are prepared. **No training has run.** Read [measured preparation results](docs/preparation-20261004.md) and [the later experiment runbook](docs/training.md). Original baseline tags/artifacts remain available. Provider, budget, compute allocation, access controls and operational retention policy are pending; see [TASKS.md](TASKS.md).

## Licenses and primary references

Application code: [MIT](LICENSE). Model weights remain under their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).

- [Ollama chat API](https://docs.ollama.com/api/chat): structured format, thinking switch, token settings and completion metadata.
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
- [Ollama Qwen3:1.7b artifact](https://ollama.com/library/qwen3:1.7b).
- [Ollama FAQ](https://docs.ollama.com/faq): localhost binding, model residency and cloud configuration.

## Submission readiness

See [readiness handoff](readiness/READINESS.md) for the cold offline test, hosting budget and prepared HTTPS packaging, sourced deadline, and team capture checklist. Offline and hosted success remain pending actual execution/user observations; no training or clinical-quality claim is implied.

## Clinician template v0.6

[Implementation, exact automatic/manual field policy, real DEV-002 failures and verification](docs/v06.md). DEV-002 has 1,620 source characters preserved verbatim; its original v0.5 reference stays separate. **18 of 19 source selections differed from provisional labels in the first real run; an alternative prompt failed structurally. No clinical quality claim.** Detailed observations, referral type and treatment rows are manual with separate source suggestions. All labels remain unreviewed; no training export or held-out evaluation used DEV-002.

## Bounded extraction recovery

[Recovery audit, controlled results and concise printing](docs/extraction-recovery-v06.md): the installed 4B Thinking-2507 comparator and one five-group 1.7B design both remained unsuitable for broad v0.6 assignment on unreviewed development fixtures. **Serving defaults are unchanged.** Exact/missing/extra assignments, all requests and raw responses are preserved. A normally completed DEV-002 print fixture now uses two readable pages, separately from the three-page long-text stress check. No clinical validation, training, new model download or deployment is implied.
