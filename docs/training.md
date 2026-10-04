# Optional fine-tuning: bounded follow-up, not performed

Prerequisites: clinically reviewed train/development examples, a preserved held-out test set grouped by underlying case, a saved baseline, and a tiny verified training-to-serving experiment. Keep the base Ollama artifact installed for rollback. A tuned candidate must preserve the exact source-ID extraction contract and pass the same validators and review UI.

## Canonical dataset

A JSON array of records:

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

The only source segmentation is `app.core.segment`/`prepare`, shared by serving, comparison and export. Offsets are Python Unicode code points. Labels reference exact units; never relabel against a separately split note. Any source edit may change IDs and needs renewed review. Both source and versions are stored. Field assignment schema is the same `config/output.source-id-1.json` contract used for serving; no competing generated-referral training target exists.

```sh
.venv/bin/python -m scripts.dataset private/all-splits.json
.venv/bin/python -m scripts.dataset private/all-splits.json --export-mlx .runtime/mlx-export-v1
```

Always supply **all splits** together, including held-out case IDs, for leakage checking. Validator rejects duplicate IDs, wrong schema/segmentation versions, malformed/invalid assignments, underlying-case cross-split overlap, and exact-note cross-split duplicates. It cannot detect paraphrases assigned misleading underlying IDs, unknown datasets outside its input, or false human review claims.

Exporter includes **reviewed train/development only**, writes `train.jsonl` / `valid.jsonl` and a provenance manifest, and excludes rejected, unreviewed and test examples. It refuses to overwrite an existing directory and refuses an all-unreviewed export. Empty splits are omitted for compatibility. A valid export alone does not establish sufficient training data; require both reviewed train and development sets before training. Held-out tests never go to training or prompt iteration.

## Trainer requirements verified without installation

The pre-existing Anaconda environment had MLX 0.30.6, MLX-LM 0.30.7, MLX-VLM 0.3.12, Transformers 5.2.0, Torch 2.9.1, datasets 4.4.1, Hugging Face Hub 1.4.1. PEFT was absent and is not needed for this proposed MLX path. No second training environment was installed and no weights were loaded by MLX.

Inspected the installed MLX-LM 0.30.7 `tuner/datasets.py` and [matching upstream source](https://github.com/ml-explore/mlx-lm/blob/v0.30.7/mlx_lm/tuner/datasets.py): it reads newline-delimited `{"messages":[...]}` with system/user/assistant roles; local files are `train.jsonl`, `valid.jsonl`, `test.jsonl`. The exporter writes the exact serving system prompt and prepared user message, then the expected assignment JSON as assistant content. `--mask-prompt` is supported for chat data. Dataset export is format validation only, not a training claim.

## Experiment before any full training

1. Clinician-review a small, separate synthetic train/development set; preserve grouped held-out tests. Record base model revision, tokenizer, prompt/schema versions and dependency versions.
2. In the existing MLX environment, verify a tiny MLX operation and base model load. Create/use a compatible 4-bit MLX Qwen3-1.7B copy. Run 5–10 LoRA iterations, batch 1, sequence 256–512, rank 4–8, few adapted layers. Track peak memory; do not silently truncate training examples.
3. Verify chat-template parity. The inspected MLX ChatDataset calls `apply_chat_template` without `enable_thinking=False`; the Ollama baseline explicitly disables thinking. A tokenizer/template/config adjustment may be necessary. Do not assume exported chat JSON alone fixes thinking-mode parity.
4. Reload adapter; use MLX fuse/dequantize to save floating-point safetensors. **MLX's installed built-in GGUF exporter excludes Qwen3. An MLX adapter is not assumed directly usable by Ollama/llama.cpp.**
5. Separately verify the exact pinned llama.cpp converter supports the merged Qwen3 weight names/config/tokenizer. Convert to F16 GGUF, quantize to Q4_K_M, and import as a new local Ollama model with a compatible non-thinking chat template. Never replace the base tag.
6. Compare adapter, merged model, F16 GGUF and quantized serving outputs, then run the unchanged application validator/comparison fixtures. Check export quality drift, provenance, categorization, omissions, limits and latency. Only then plan full training.

Unverified: MLX runtime on this machine today; rank/memory budget; chat-template masking parity; whether this exact merged checkpoint converts cleanly; tied embedding/config/tokenizer compatibility; quantization impact; import/template behavior; whether training improves Mongolian extraction at all. No model conversion or training was attempted.

References: [MLX LoRA/fuse documentation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md), [llama.cpp Qwen3 converter](https://github.com/ggml-org/llama.cpp/blob/master/conversion/qwen.py), [GGUF quantization](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md). Documentation support for individual steps does not verify the whole pipeline.
