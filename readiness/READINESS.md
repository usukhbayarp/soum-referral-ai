# Readiness handoff — 2026-10-04

- **Observed:** project `/Users/usukhbayar.purevdorj/Documents/hackathon`, branch main; existing application running at localhost:8000. No active project download/conversion observed; Ollama had no resident model at inspection. Shared Ollama desktop service left running. Apple M4, 10 CPU cores, 16 GiB unified memory, macOS 15.1 arm64. No training, conversion, model comparison or inference on the new note performed in this readiness patch.
- **Prepared / user action needed:** [cold offline test](OFFLINE-TEST.md), new unreviewed development-only [fictional fixture](fixtures/offline-new.json), and `python -m scripts.offline_test`. Local evidence stays in ignored `.runtime/offline-readiness-v06`. Before/after snapshots and API results are separate from user observations; all manual steps start `not_run`. Offline success has not been demonstrated by this patch.
- **Prepared / approval pending:** [hosting options, cost controls and deployment commands](HOSTING.md), HTTPS proxy and Compose override. No paid resources, public tunnel or hosted deployment created. Baseline model tags retained; app/prompt/schema/training pipeline unchanged.
- **Documentation-supported:** [submission deadline and unresolved requirements](SUBMISSION.md). Public cutoff **Oct 4 at 21:00 Ulaanbaatar**. The organizer video clarification is recorded: Team Intro, Demo, Teach, each ≤60s; no additional long video. No submission/organizer message sent.
- **Prepared:** [45–55-second team script and real-photo checklist](TEAM-CAPTURE.md); names/affiliations remain placeholders, personal media stays private.

## User handoff, after independent preparation

1. Reserve a short window when no other application needs shared Ollama. Follow the saved offline guide; manually disconnect all uplinks, restart/test, reconnect and record actual observations. The assistant cannot remain reliably available while you are disconnected. Do not call the test passed before those results exist.
2. Supply any current portal deadline override (screenshot or exact text). Confirm required demo hosting retention period if known.
3. Approve or change the proposed DO configuration, $30 maximum authorized spend and seven-day duration; supply account availability and an owned DNS hostname. No credentials needed in chat. This budget is not a provider-enforced spending cap.
4. Replace team placeholders, record both actual members and retain originals privately. User handles upload/submission after checking every link and field.

Regression/unit checks validate the harness and packaging only; they are not offline, hosted, performance or clinical validation. See commit handoff for actual test counts.

## Preparation checks actually run

- Python regression suite: **66 passed** (one existing Starlette/AnyIO deprecation warning). Includes new harness guards and fixture validation; no model inference in these tests.
- JavaScript state regressions: **13 passed**.
- Merged Compose configuration validated; checked shared loopback namespace, explicit allowed host, hosted disclosure and absence of an exposed inference port.
- Caddy 2.10.2 configuration validated in a disposable container with `--network none`, no published ports; image downloaded and pinned by digest. The validator exited successfully; no proxy server/deployment started.
- `git diff --check` passed. Offline test, PDF visual inspection, public HTTPS issuance, cloud latency/capacity and cloud billing remain untested.

## v0.6 update

See [implementation and development results](../docs/v06.md). The clinician-designed template is integrated but remains unofficial, experimental and unapproved by receiving clinicians. DEV-002 is AI-generated, fictional, development-only and unreviewed. One receiving doctor reported unclear treatment information and contacting sending doctors for clarification: **one qualitative interview**, not measured prevalence or proven patient-outcome impact. Sending-clinic digital-note availability and hardware remain unverified. The prior network-disconnected restart → extraction → edit → approval → print test remains **unproven**; prepare a new version-recorded bundle. No hosting/training started.

## v0.7 update

The authoritative clinician-approved form scope is implemented; see [v0.7 mapping and checks](../docs/v07.md). It remains experimental/unofficial. Existing 19-category extraction limitations remain disclosed; no experimental extractor or serving-model replacement is activated. The original Qwen3-4B comparison is a fictional, unreviewed development mechanics experiment, separate from the form release. Offline restart, hosted deployment, clinical validation and time saved remain unclaimed. Required videos remain **exactly three separate videos, each ≤60 seconds: Team Intro, Demo, Teach**. Paid deployment and submission remain pending user action.
