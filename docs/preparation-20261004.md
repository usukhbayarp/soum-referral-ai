# Optional training/export and packaging observations — 2026-10-04

**Observed:** continued from `c7276998878dea7e651eeefe60364b8d3b5b951b` on `main`. Preparation began at 05:59:27 UTC. The untuned model completed serving checks about 15 minutes later, inside the approximately 45-minute export timebox. No optimizer steps, full training, paid provisioning or hosted deployment occurred. The existing localhost demo process was left running. Prompts, schemas, UI, previous baseline reports and pre-existing model digests were preserved.

## Environment and reusable assets

**Observed:** Apple M4 / macOS 15.1 / 16 GiB unified memory; existing Anaconda Python 3.13.5 with MLX 0.30.6, MLX-Metal 0.30.6, MLX-LM 0.30.7, MLX-VLM 0.3.12, Transformers 5.2.0, Torch 2.9.1, datasets 4.4.1 and Hugging Face Hub 1.4.1. Tiny MLX GPU arithmetic succeeded. Anaconda's optional `readline` extension crashes with exit 139; the repository's noninteractive wrapper avoids importing it without modifying installed packages. Details and the resolved Git HTTP/2 download failure are in [export provenance](../evaluation/preparation/export-provenance-20261004.json).

**Observed:** downloaded only the missing `Qwen/Qwen3-1.7B` snapshot at `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` through the standard HF cache. Both original shards are complete (4,063,515,592 bytes combined). Original cache retained; MLX affine 4-bit/group-64 copy retained at `.runtime/preparation/qwen3-1.7b-mlx4`, 979,558,840 bytes before its small provenance file. Quantization reported 4.501 bits/weight. Exact versions, revision, file hashes and tokenizer hashes are recorded, not inferred from a model tag.

**Observed:** initial free disk was approximately 13 GiB. F16 and dequantized intermediates were hashed and removed only after their subsequent stages succeeded. Existing caches were not deleted. About 4.6 GiB remained after the new base, MLX copy, Q4 export, Ollama import, build tools and image. **Estimated:** later adapter fusion/export needs several additional GiB of temporary space; stage and remove only newly generated intermediates after verification. **Untested:** actual LoRA peak memory and throughput. Fitting untuned conversion/inference does not prove full-sequence training fits this Mac.

## Route actually executed

**Observed, successful:** pinned upstream safetensors → MLX 4-bit → MLX dequantized BF16 safetensors → pinned llama.cpp F16 GGUF → Q4_K_M → new Ollama tag. This is an **untuned lossy round trip**, not restoration of the original weights. No MLX built-in GGUF exporter was used.

```sh
python -m scripts.mlx_python mlx_lm convert \
  --hf-path "$(cat .runtime/preparation/base-path.txt)" \
  --mlx-path .runtime/preparation/qwen3-1.7b-mlx4 -q --q-bits 4 --q-group-size 64
python -m scripts.mlx_python mlx_lm convert \
  --hf-path .runtime/preparation/qwen3-1.7b-mlx4 \
  --mlx-path .runtime/preparation/qwen3-1.7b-dequantized --dequantize
.runtime/preparation/converter-env/bin/python -m scripts.mlx_python --script \
  .runtime/preparation/llama.cpp/convert_hf_to_gguf.py \
  .runtime/preparation/qwen3-1.7b-dequantized \
  --outfile .runtime/preparation/untuned-control-f16.gguf --outtype f16
.runtime/preparation/llama.cpp/build/bin/llama-quantize \
  .runtime/preparation/untuned-control-f16.gguf \
  .runtime/preparation/untuned-control-Q4_K_M.gguf Q4_K_M 4
.venv/bin/python -m scripts.import_candidate \
  --gguf .runtime/preparation/untuned-control-Q4_K_M.gguf \
  --tag soum-qwen3-1.7b-untuned-control:mlx4-roundtrip-20261004 \
  --output .runtime/preparation/control-import
```

These are the successful command shapes; they intentionally refuse or are unsuitable for overwriting existing output directories/tags. The temporary dequantized weight and F16 GGUF were removed after verification. Logs and retained small metadata are under ignored `.runtime/preparation/`.

**Observed:** converter/build commit `11fe02151f79c41d0d4af7da708755d73b9c0da6`; CMake 4.1.3 in an isolated overlay; CPU-only quantizer build succeeded. F16 output: 3,447,349,248 bytes. Q4_K_M output: **1,107,408,896 bytes**, SHA-256 `810430e69414d418850f4c51bfe9374b06df55be288bdbc42f88fb20b9630de3`; quantization took **28.14 seconds**. Ollama 0.34.0 imported it as `soum-qwen3-1.7b-untuned-control:mlx4-roundtrip-20261004`, digest `e6a6e54bcc9d597d1700b25e24e5b769ca18333015079b50ead7ecaa269bfa75`. The running application still selects `qwen3:1.7b`.

**Observed:** upstream `model.embed_tokens.weight` and `lm_head.weight` are byte-identical (recorded tensor hashes). MLX's Qwen3 sanitizer drops the duplicate head when `tie_word_embeddings=true`. This control stores 1,720,574,976 parameters, whereas the cached Ollama baseline metadata counts 2,031,739,904. This accounts for the storage-count difference; it does not establish numerical parity after two quantization stages. The cached baseline's exact upstream checkpoint revision remains unknown.

## Tokenization and control comparison

**Observed:** [serving-aligned token audit](../evaluation/preparation/serving-token-audit-20261004.json) verifies non-thinking prefix, complete assistant JSON/EOS masking and prompt/padding exclusion. Full sequence lengths are 1,321–1,572 tokens; measured prompt counts match Ollama on every case. Raw HF rendering without the Ollama transport additions was four tokens shorter, preserved in the earlier [raw-HF audit](../evaluation/preparation/token-audit-20261004.json). Original HF and saved MLX token sequences match under the same policy. Every future reviewed example is measured separately; no examples are truncated.

**Observed:** the five unchanged fictional development cases were run once on the control. The prior baseline was compared from its preserved report, not rerun. See [raw control outputs](../evaluation/untuned-control/comparison-20261004T061310Z.json) and [mechanics differences](../evaluation/untuned-control/mechanics-diff-20261004.json).

| Mechanical result | Preserved baseline | Untuned control |
|---|---:|---:|
| Structurally valid outputs | 5/5 | 5/5 |
| Invalid outputs | 0 | 0 |
| Fields reported not found | 11/35 | 20/35 |
| Mean latency in these runs | 4.723 s | 3.881 s |

Only **1/5 complete assignment sets agree**. Go template hashes, runtime version, prompt counts and explicit inference settings match. Differences in artifact precision, embedding representation and conversion remain; no single cause was isolated. Latency samples were taken at different times and do not establish a performance improvement. The converter's automatically inferred metadata includes `general.finetune=dequantized`; that string is a directory-name artifact, **not evidence of fine-tuning**. Training steps were zero.

**Untested:** clinical correctness and Mongolian extraction quality. All five fixtures remain unreviewed. JSON validity, agreement and abstention counts cannot answer clinical questions. The control is now preserved to separate future training effects from conversion effects.

## Prepared code and verification

**Observed:** 51 Python tests and 13 Node state tests passed. Focused coverage includes split prerequisites, tag protection, model/tokenizer tamper detection, immutable canonical messages under template rendering, invalid-output retention, liveness independent of Ollama and model-readiness errors. The actual MLX tokenizer/loss probes passed without training. Current unreviewed fixtures were rejected by training preflight. The existing Starlette/AnyIO deprecation warning remains.

**Observed:** Compose validates with an explicit hostname allowlist. ARM64 web image built (232,276,320 bytes), digest `sha256:7f802401d627c309ebfc8fe64a986f5b4ecf77cb70c8b10e833afef80e45c1a7`; offline read-only container import succeeded. **Prepared, not deployed:** hosted disclosure, shared-loopback network arrangement, one worker, bounded inference, no Docker/access-log persistence and separate `/api/health` versus `/api/ready`. The latter checks installed model availability without loading it; an inference smoke is a separate acceptance step. See [deployment runbook](deployment.md).

## Remaining blockers and next action

**Blocked pending human inputs:** final schema/form approval; genuinely clinician-reviewed, disjoint training/development data; a preserved held-out test set. Provider, region, budget, access policy and capacity targets are also needed before hosting. No further model downloads or full training are justified by these unreviewed fixtures.

**Untested next experiment:** five optimizer steps, adapter reload/fusion and adapted-MLX → F16 → Q4 numerical/behavioral checks. The runnable skeleton and development-loss checkpoint selection are prepared, but have not been executed. Keep the original baseline for rollback and use the same extraction contract.

Once reviewed data is at `private/all-splits.json`, the next command is **preflight only**:

```sh
/opt/anaconda3/bin/python -m scripts.mlx_python scripts.training_prepare \
  private/all-splits.json --output .runtime/experiments/smoke-001
```

Training requires the separate, explicit later command in [training.md](training.md). No claims of tuned quality or a tested hosted deployment are made.
