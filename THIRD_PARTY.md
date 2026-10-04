# Third-party acknowledgments

The application MIT license applies to this repository's application code, not to model weights or external libraries. No model weights are distributed here.

- Qwen3 models: Alibaba/Qwen, Apache License 2.0. [Qwen3-1.7B license](https://huggingface.co/Qwen/Qwen3-1.7B/blob/main/LICENSE). The cached 4B identifies [Qwen3-4B-Thinking-2507](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507/blob/main/LICENSE) in its GGUF metadata. Ollama distribution templates/quantizations retain their applicable upstream notices. Exact downloaded digests are in evaluation results.
- Ollama: MIT; https://github.com/ollama/ollama/blob/main/LICENSE. Used as a separately installed runtime.
- FastAPI, Pydantic, pytest, pytest-asyncio: MIT; see their installed distribution metadata and upstream licenses.
- Starlette, Uvicorn, HTTPX, httpcore: BSD-3-Clause; see installed distribution metadata and upstream licenses.
- Remaining transitive dependencies retain their respective licenses; exact installed versions are in requirements-lock.txt. No third-party code is vendored.
- System fonts are used via CSS and are not redistributed. UI requires no external assets.
- Optional future MLX/MLX-LM use and llama.cpp conversion have their own upstream licenses; neither models nor training libraries are bundled here.
