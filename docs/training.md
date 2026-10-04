# Optional fine-tuning: clinical training pending

Latest: [v0.8 partial review and recovered export](clinician-partial-v08.md). Partial annotations are evaluation-only and rejected by whole-note training export. The proposed home/pre-encounter contract is not active; resolve representation and obtain separate fully reviewed training data before a quality pilot.
The earlier [original-4B engineering smoke](pipeline4b-smoke.md) verified three optimizer steps, reload and adapter-layer fusion. Untuned 4B export/import succeeded; smoke full export initially stopped at critical memory pressure and was subsequently recovered through two-tensor fusion and sparse HF replacement. No reviewed-data clinical experiment has run. The production-contract workflow below remains separate from experimental A-v2.

Prerequisites: clinically reviewed train/development examples, a preserved held-out test set grouped by underlying case, a saved baseline, and a tiny verified training-to-serving experiment. Keep the base Ollama artifact installed for rollback. A tuned candidate must preserve the exact source-ID extraction contract and pass the same validators and review UI.

## Canonical dataset

A JSON array of records. The snippet below is a **historical v0.1** example retained for compatibility; new v0.6 records must use `schema_version: experimental-0.6`, explicit `prompt_version: source-id-v06-1`, and all 19 keys from `config/output.source-id-v06-1.json`. See `evaluation/dev002-v06/cases.json` for the exact current shape (unreviewed development only).

```json
{
  "case_id": "case-001-variant-a",
  "underlying_case_id": "case-001",
  "source_note": "Халуураагүй. Эмийн харшилгүй.",
  "expected_assignments": {
    "history": [1], "examination": [], "investigations": [],
    "diagnosis": [], "medication": [], "allergies": [2], "referral": []
  },
  "schema_version": "provisional-0.1",
  "segmentation_version": "sentence-lines-1",
  "split": "train",
  "synthetic_origin": "fictional example authored for documentation only",
  "clinician_review_status": "unreviewed",
  "scenario": "optional description"
}
```

This example is **not reviewed**. `expected_assignments` may be null for unreviewed fixtures; reviewed records require complete labels. Review status values: `unreviewed`, `reviewed`, `rejected`. `split`: `train`, `development`, `test`. Synthetic origin must describe provenance; human review must ensure it is genuinely fictional. Marking `reviewed` is a human attestation, not something the tool can verify.

The only source segmentation is `app.core.segment`/`prepare`, shared by serving, comparison and export. Offsets are Python Unicode code points. Labels reference exact units; never relabel against a separately split note. Any source edit may change IDs and needs renewed review. Both source and versions are stored. Field assignment schema is the same version-selected contract used for serving (`output.source-id-v06-1.json` for v0.6, `output.source-id-1.json` for historical v0.1); no competing generated-referral training target exists.

```sh
.venv/bin/python -m scripts.dataset private/all-splits.json
.venv/bin/python -m scripts.dataset private/all-splits.json --export-mlx .runtime/mlx-export-v1
```

Always supply **all splits** together, including held-out case IDs, for leakage checking. Validator rejects duplicate IDs, wrong schema/segmentation versions, malformed/invalid assignments, underlying-case cross-split overlap, and exact-note cross-split duplicates. It cannot detect paraphrases assigned misleading underlying IDs, unknown datasets outside its input, or false human review claims.

Exporter includes **reviewed train/development only**, writes `train.jsonl` / `valid.jsonl` and a provenance manifest, and excludes rejected, unreviewed and test examples. It refuses to overwrite an existing directory and refuses an all-unreviewed export. Empty splits are omitted for compatibility. A valid export alone does not establish sufficient training data; require both reviewed train and development sets before training. Held-out tests never go to training or prompt iteration.

## Environment and pins (observed, 2026-10-04)

Reuse `/opt/anaconda3/bin/python` (3.13.5): MLX 0.30.6, MLX-Metal 0.30.6, MLX-LM 0.30.7, MLX-VLM 0.3.12, Transformers 5.2.0, Torch 2.9.1, datasets 4.4.1, Hugging Face Hub 1.4.1. A GPU array square returned `[1,4,9]`. No second MLX stack was installed. This environment's optional `readline` extension segfaults even on `import readline`; `scripts.mlx_python` disables that extension **only in its noninteractive process**. Transformers, tokenization and MLX conversion then succeeded. It does not repair or modify Anaconda.

`training/pins.json` pins both upstream weights and tokenizer to **Qwen/Qwen3-1.7B @ 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e**, and llama.cpp to **11fe02151f79c41d0d4af7da708755d73b9c0da6**. The original HF cache is retained. The ready MLX copy is `.runtime/preparation/qwen3-1.7b-mlx4` (affine 4-bit, group 64, approximately 980 MB including tokenizer). Its `preparation-provenance.json` records file hashes, revision and versions. Do not regenerate it unnecessarily.

The isolated `.runtime/preparation/converter-env` inherits installed Python packages read-only using `venv --system-site-packages`; CMake 4.1.3 was installed into that overlay. The converter used its own pinned `gguf-py` 0.19.0 source, inherited Torch 2.9.1 / Transformers 5.2.0 / NumPy 1.26.4, and the CPU quantizer built with AppleClang 16.0.0. This tested Qwen3 subset differs from the converter's broad requirements (Torch 2.11.0, Transformers 4.57.6, NumPy ~2.2.6); it is **not a claim that every converter architecture works**. No global dependencies were upgraded.

## Template, lengths and masking (observed)

The installed [MLX ChatDataset](https://github.com/ml-explore/mlx-lm/blob/v0.30.7/mlx_lm/tuner/datasets.py) reads the canonical `messages` JSONL, but does not pass `enable_thinking=False`. Our wrapper passes that option and mirrors the preserved Ollama template's extra system newline and final-user ` /no_think` suffix. This transport policy is `ollama-qwen3-single-turn-1`; it changes neither the versioned extraction prompt nor canonical exported messages. It supports only this application's system/user/assistant exchange.

Every example checks that the full training tokens start with the exact inference prefix and that the unmasked suffix is precisely assignment JSON plus `<|im_end|>\n`. The pinned HF and saved MLX tokenizers produced identical full sequences and mask boundaries for all five fixtures. Serving-aligned prompt counts match both recorded Ollama runs. Raw HF rendering was four tokens shorter; both audits are preserved under `evaluation/preparation/`.

Measured full prompt-plus-target lengths are **1,321, 1,420, 1,451, 1,563 and 1,572 tokens** (five fictional notes, baseline outputs as mechanical targets; not reviewed labels). A 512-token limit would truncate every one. `training_prepare` measures **every reviewed record**, rounds the largest full length up to 32, rejects a sequence beyond serving context, and records all lengths. The runner rechecks lengths and refuses truncation. Larger real reviewed examples may need more memory; these measurements are not a maximum-input guarantee.

The installed [MLX loss](https://github.com/ml-explore/mlx-lm/blob/v0.30.7/mlx_lm/tuner/trainer.py) uses an inclusive end boundary that can include a padding target. `completion_loss` uses an exclusive end: prompt and padding are masked; JSON and EOS are trained. A numerical dummy-logit test verified exactly two real completion targets, with no optimizer or model update. Do **not** bypass this runner with a plain `mlx_lm lora --mask-prompt` command: it would omit our template and padding checks.

## v0.6 compatibility

No training or conversion was started for v0.6. DEV-002 and any reordered/abbreviated variant must keep underlying_case_id `DEV-002` and split `development`; all are unreviewed and ineligible for reviewed-only export. Its source mapping is provisional, not a clinical benchmark. The current tokenizer/masking check measured 2,624 prompt + 163 target = **2,787 tokens** under the unchanged 16,384 context; the rejected prompt variant measured 3,217. These are measurements for one development case, not universal limits. No truncation is permitted. The preparation command requires separate reviewed train/development sets plus a held-out set, all matching the active explicit contract. Export rejects mixed contracts; historical files/reports are not relabeled. `training_audit` is historical-only and now refuses mismatched active versions. Use `scripts.dev002_tokens` for v0.6 tokenization mechanics.

The existing conversion preparation and untuned-control tag remain untouched. New training cannot be justified by this unreviewed example or the failed development extraction. Reviewed labels, baseline, held-out set and a tiny training-to-serving experiment are still prerequisites.

## Exact next command when reviewed data arrives

Place the canonical **all-splits** dataset at `private/all-splits.json`, with actual clinician-reviewed training and development records and a preserved held-out test set. From the repository root:

```sh
/opt/anaconda3/bin/python -m scripts.mlx_python scripts.training_prepare \
  private/all-splits.json --output .runtime/experiments/smoke-001
```

This command **only validates, exports and measures**. It requires nonempty reviewed train and development sets, checks underlying-case leakage across all supplied splits, excludes all test/unreviewed/rejected records, verifies the model file hashes and refuses an existing destination. It never changes review status. The current all-unreviewed fixtures correctly fail with `Separate reviewed train examples are required`.

Outputs: `data/train.jsonl`, `data/valid.jsonl`, canonical `data/manifest.json`, measured `smoke.json`, and `preflight.json` containing input/export/model/code/contract hashes, versions and token lengths. Review these before the experiment. No test text is exported. Hashes protect local reproducibility, not the truth of human review attestations.

## Later five-step experiment — NOT executed

After final schema approval and reviewed-data preflight:

```sh
/opt/anaconda3/bin/python -m scripts.mlx_python scripts.training_smoke \
  .runtime/experiments/smoke-001 --schema-approved
```

`training/smoke.json` supplies batch 1, rank 4, four adapted layers, five steps, gradient checkpointing and seed 42. The sequence limit comes from measured data, not a fixed short default. The runner rejects changes to prepared data, model, tokenizer, selected prompt, contract, template policy or runner code; repeat preflight after any change. It writes adapters/checkpoints, content-free loss/memory metrics and `best/selection.json`. Selection minimizes **all reviewed-development completion loss**, never held-out loss or JSON-validity counts. Because MLX validates before each step, a final post-step evaluation is explicit; the untuned zero-step checkpoint can legitimately win. This is a candidate-selection proxy, not a clinical metric.

Then reload/fuse the selected adapter and test serving. These are later commands, not a record of completed training:

```sh
/opt/anaconda3/bin/python -m scripts.mlx_python mlx_lm fuse \
  --model .runtime/preparation/qwen3-1.7b-mlx4 \
  --adapter-path .runtime/experiments/smoke-001/best \
  --save-path .runtime/experiments/smoke-001/fused --dequantize

.runtime/preparation/converter-env/bin/python -m scripts.mlx_python --script \
  .runtime/preparation/llama.cpp/convert_hf_to_gguf.py \
  .runtime/experiments/smoke-001/fused \
  --outfile .runtime/experiments/smoke-001/candidate-f16.gguf --outtype f16

.runtime/preparation/llama.cpp/build/bin/llama-quantize \
  .runtime/experiments/smoke-001/candidate-f16.gguf \
  .runtime/experiments/smoke-001/candidate-Q4_K_M.gguf Q4_K_M 4

.venv/bin/python -m scripts.import_candidate \
  --gguf .runtime/experiments/smoke-001/candidate-Q4_K_M.gguf \
  --tag soum-qwen3-1.7b-candidate:smoke-001 \
  --output .runtime/experiments/smoke-001/import

.venv/bin/python -m scripts.compare \
  --models soum-qwen3-1.7b-candidate:smoke-001 \
  --output .runtime/experiments/smoke-001/comparison
```

The importer refuses existing tags, uses the preserved baseline Go template, and verifies all pre-existing digests after import. Record converter revision (`git -C .runtime/preparation/llama.cpp rev-parse HEAD`) against `training/pins.json` before conversion; do not update that checkout silently. Use `scripts.compare_reports BASELINE_REPORT CANDIDATE_REPORT --baseline-model MODEL --candidate-model MODEL --output NEW_REPORT` against both the saved untuned control and original baseline. It rejects case/settings/contract mismatch and retains invalid outputs and abstentions. The fixed fictional comparison remains a mechanics check; add clinician-scored reviewed development evaluation before selecting a trained model. Do not use held-out tests for iteration.

**Untested:** actual optimizer steps, adapter reload/fusion, numerical parity between adapted MLX and fused/F16/Q4 runtimes, training peak memory, and clinical quality. The untuned export verifies the conversion route but does not prove adapter fusion correct. Evaluate tuned-vs-control to separate training effects from conversion effects; round-trip 4-bit → floating point → Q4 is lossy, not recovery of original precision. See [preparation observations](preparation-20261004.md).

Rollback needs no model download: keep `qwen3:1.7b` installed and set `REFERRAL_MODEL=qwen3:1.7b` on the next deliberate app restart. Importing a candidate never changes the running app. Prefer deleting only explicitly identified, newly generated intermediate exports after recording hashes; do not delete baseline caches. Later merge/export needs several additional GiB of temporary storage; current available space is recorded in the preparation report.

## Primary sources

- [Pinned upstream model/tokenizer](https://huggingface.co/Qwen/Qwen3-1.7B/tree/70d244cc86ccca08cf5af4e1e306ecf908b1ad5e).
- [MLX 0.30.7 conversion](https://github.com/ml-explore/mlx-lm/blob/v0.30.7/mlx_lm/convert.py) and [adapter fuse](https://github.com/ml-explore/mlx-lm/blob/v0.30.7/mlx_lm/fuse.py): floating-point safetensors are the interchange. Its built-in GGUF branch supports only llama/mixtral/mistral; **never use `--export-gguf` for Qwen3**.
- [Pinned llama.cpp Qwen3 converter](https://github.com/ggml-org/llama.cpp/blob/11fe02151f79c41d0d4af7da708755d73b9c0da6/conversion/qwen.py) and [quantization tool](https://github.com/ggml-org/llama.cpp/blob/11fe02151f79c41d0d4af7da708755d73b9c0da6/tools/quantize/README.md).
- [Ollama GGUF import](https://docs.ollama.com/import): import the already-quantized GGUF under a separate model name. An MLX adapter is not directly imported into Ollama.

## v0.7 / prospective original 4B (2026-10-04)

The form update does not change the existing 19-category source-assignment training contract. Keep its reviewed-data exporter and separate reviewed train/development families; held-out content was not opened for this milestone. The medication A/B formats remain experimental, frozen and **not drop-in inputs** to that exporter. See the new human clinician sheet and annotation guidance in `evaluation/original4b-v07`; no current fixture is training eligible.

The existing MLX 0.30.6 / MLX-LM 0.30.7 / Transformers 5.2.0 environment is reused. Source inspection confirms Qwen3 attention `q_proj/k_proj/v_proj/o_proj` and MLP linear modules. With no explicit `keys`, installed `linear_to_lora_layers` targets eligible linear/embedding modules discovered in the last configured blocks, **not just q/v**. The five-step skeleton uses rank 4, last four blocks, batch 1, completion-only masking and measured sequence lengths. Prospective original 4B has 36 blocks / hidden 2560, versus 1.7B's 28 / 2048: model-class compatibility is supported by source, actual allocation/LoRA conversion and training peak memory remain untested. No 4B full-precision checkpoint or training weights downloaded.

The pinned 4B tokenizer and token-mask report are stored separately; do not assume tokenizer byte identity from the common model family. The 1.7B export route remains the reusable starting point: MLX fuse with dequantized HF-compatible safetensors → pinned llama.cpp F16 GGUF → Q4_K_M → new Ollama tag. Actual adapted fusion/parity and the full 4B route remain unverified. The publisher's original-4B GGUF is a model comparison reference, **not a conversion-matched control for a future MLX-trained 4B**. Before training, pin a chosen 4B source-weight revision and create its own untuned MLX round-trip control; do not substitute the publisher GGUF for that control. Retain qwen3:1.7b rollback and every existing tag.

Next prerequisites: explicit clinician review and corrections, representation/contract selection, separate reviewed train/development families, immutable held-out families, measured full sequences, and an authorized tiny training→fusion→serving experiment. No training automatically follows receipt of files. Preserve Apache-2.0 notices when distributing weights. Training remains a viable follow-up, not rejected because of the deadline.

## Later bounded original-4B verification

[Observed engineering-only smoke, untuned control and blocked smoke export](pipeline4b-smoke.md): three real optimizer steps, saved adapter reload, adapter inference and adapter-layer fusion succeeded using the official pinned MLX 4-bit source. This does not validate clinical training or the complete 4B training-to-Ollama route. New private A-v2 correction/export/preflight tooling preserves the frozen role task; it does not repurpose the production 19-category dataset schema. No reviewed-data experiment has run.
