# Original Qwen3-4B: observed provenance and limits

Official publisher: [Qwen/Qwen3-4B-GGUF, pinned revision](https://huggingface.co/Qwen/Qwen3-4B-GGUF/tree/bc640142c66e1fdd12af0bd68f40445458f3869b). The publisher manifest/card identifies base model **Qwen/Qwen3-4B**, Apache-2.0. Commit history is May 2025, before Thinking-2507. This is neither the existing local Thinking-2507 alias nor VL.

Artifact `Qwen3-4B-Q4_K_M.gguf`, **2,497,280,256 bytes**, SHA256 **7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5**, downloaded from the commit-specific resolve URL and verified against the publisher LFS manifest. No mutable alias was used to choose bytes. [Original upstream inspected revision](https://huggingface.co/Qwen/Qwen3-4B/tree/1cfa9a7208912126459214e8b04321603b3df60c) is a metadata/tokenizer pin, **not proof of the quantizer's input revision**. The exact source-weight revision and conversion recipe are unpublished in the inspected manifest/card.

GGUF inspection: qwen3 architecture, 36 blocks, hidden size 2560, context metadata 40960, file type 15 (Q4_K_M), 398 tensors. Internal `general.name` is **Qwen3 4B Instruct Awq**, `general.finetune` **Instruct-awq**. This discrepancy is retained, not rewritten: original-family identity rests on Qwen's official manifest/history plus architecture, not the internal name alone. Do not claim direct full-precision quantization or numerical parity.

New local tag: **soum-qwen3-4b-original:q4_k_m-bc640142**. Import recorded every pre-existing digest and verified preservation. `import/import.json` records the new Ollama digest. Apache license notice is included. The downloaded GGUF and Ollama blob remain local/ignored; no weights are committed.

Embedded Jinja differs from current upstream in message-type/tool/reasoning handling (`template-diff.txt`). Both retain `enable_thinking=false` empty-think prefix. The imported Go template intentionally matches the preserved baseline template SHA256 `ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4`: single-turn system newline + user `/no_think` + empty think prefix. Token/mask checks use the same serving-render policy; the tiny `think:false` smoke stopped normally, returned the requested JSON and no reasoning. It unloaded only its own new model (`keep_alive:0`) so the first comparison began cold; all experiment calls use the required `keep_alive:"5m"`.

The inspected upstream tokenizer vocabulary/model and chat template match the existing 1.7B preparation, but serialized preprocessing/decoder metadata differs. The pinned 4B tokenizer was checked directly: complete provisional prompt+target lengths are A-v1 609–2103, B-v1 825–2503, A-v2 1696–3190, B-v2 2403–4081 tokens. Installed MLX-LM completion-mask checks passed for all 16 combinations without truncation. These are token/mask mechanics on unreviewed targets, not training or quality evidence.

Reproduce metadata inspection with the already-installed converter environment:

```sh
PYTHONPATH=.runtime/preparation/llama.cpp/gguf-py \
  .runtime/preparation/converter-env/bin/python scripts/original4b_metadata.py
```

The source script only memory-maps GGUF metadata; it does not load the model for generation. Resource preflight: 12 GiB free disk and 50% system free-memory metric before download, 16 GiB unified memory. After artifact + Ollama import, roughly 6.2 GiB disk remained. Future training/export needs additional space; no cache was deleted. Inference memory uses two-second RSS and Ollama `size_vram` samples, which must not be summed as separate physical allocations.
