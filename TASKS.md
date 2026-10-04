# Follow-up tasks

## Clinician and language review
- [ ] Review provisional field schema, required-workflow rules, Mongolian UI, print layout and workflow guidance.
- [ ] Review/correct the five fictional development notes and complete source-unit labels; score both saved model outputs.
- [ ] Establish acceptable omission/misclassification thresholds and failure behavior, with special attention to negation, medication units and temporal evidence.
- [ ] Supply realistic note length and device targets.

## Evaluation and optional tuning
- [x] Reuse MLX environment, pin base/tokenizer/converter, check completion masking and full sequence lengths, and preserve an untuned MLX-to-GGUF-to-Ollama control.
- [x] Prepare reviewed-data preflight, bounded training skeleton, development-loss selection and protected candidate import. Training has not run.
- [ ] Create reviewed synthetic train/development/test cases grouped by underlying case. Keep held-out cases out of prompt iteration.
- [ ] Freeze baseline digests, prompt/schema/segmentation versions and scoring rubric.
- [ ] Review all-empty abstentions separately from invalid responses and clinical correctness.
- [ ] Perform tiny MLX training-to-Ollama serving experiment only after prerequisites; keep baseline for rollback.
- [ ] Re-evaluate tuned GGUF under identical settings and clinician-reviewed labels before choosing it.

## Offline demonstration
- [ ] Restart app and Ollama with network disconnected with user's permission; test cold model load, extraction, editing and printing.
- [ ] Verify local-only Ollama/cloud settings and logs in the intended demo environment.
- [ ] Test Windows/Linux setup, system Cyrillic fonts, printing and performance on representative devices.
- [ ] Test maximum accepted note/output size, long print layout, abbreviations, Unicode and realistic source formats.

## Hosted demonstration (not deployed)
- [x] Prepare shared-loopback Compose packaging, hosted disclosure and separate liveness/model-availability probes; build/import-check web image. Full hosted stack remains untested.
- [ ] Select provider/region, budget, CPU/GPU/RAM and concurrent-user target.
- [ ] Provision isolated sessions, expiry/reset policy, HTTPS, explicit allowed hosts and appropriate demo access controls; use fictional data only.
- [ ] Keep Ollama on loopback/private inference boundary. Deploy one web worker initially or implement a shared bounded queue before multiple replicas.
- [ ] Add rate limits, request cancellation/disconnect handling, resource monitoring and content-free logging; test overload/session isolation.
- [ ] Document retention for browser memory, runtime memory, logs and exports. Review hosting terms and data handling.

## Hackathon submission
- [ ] Describe measured mechanics separately from unvalidated clinical performance.
- [ ] Prepare fictional walkthrough video, architecture graphic and demo script.
- [ ] Record comparison limitations and clinician contribution; avoid national-form or diagnostic claims.
- [ ] Verify submission requirements and provide repository/demo links.
