import json, hashlib
from pathlib import Path
from gguf import GGUFReader

p = Path("evaluation/original4b-v07")
assert json.loads((p / "download.json").read_text())["verified"]
r = GGUFReader(".runtime/original4b/Qwen3-4B-Q4_K_M.gguf")
meta = {}
for k, f in r.fields.items():
    if (
        k.startswith("general.")
        or k.startswith("qwen3.")
        or k
        in [
            "tokenizer.chat_template",
            "tokenizer.ggml.model",
            "tokenizer.ggml.pre",
            "tokenizer.ggml.bos_token_id",
            "tokenizer.ggml.eos_token_id",
        ]
    ):
        meta[k] = f.contents()
assert meta["general.architecture"] == "qwen3"
assert meta["qwen3.block_count"] == 36
assert "Thinking" not in meta.get("general.name", "") and "2507" not in meta.get(
    "general.name", ""
)
meta["tensor_count"] = len(r.tensors)
meta["chat_template_sha256"] = hashlib.sha256(
    meta["tokenizer.chat_template"].encode()
).hexdigest()
meta["template_matches_current_upstream"] = (
    meta["tokenizer.chat_template"]
    == json.loads((p / "Qwen3-4B-tokenizer_config.json").read_text())["chat_template"]
)
(p / "gguf-metadata.json").write_text(json.dumps(meta, indent=2))
print({k: v for k, v in meta.items() if k != "tokenizer.chat_template"})
