"""Replaceable local model adapter. Never logs note/model content."""

import asyncio
import json
import os
import re
from urllib.parse import urlparse
import httpx
from .core import (
    ExtractionError,
    PROMPT_VERSION,
    OUTPUT_SCHEMA_VERSION,
    SEGMENTATION_VERSION,
    SYSTEM,
    SCHEMA,
    prepare,
    resolve,
)

OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 16384, "num_predict": 1600}


class OllamaAdapter:
    def __init__(self, model=None, base_url=None, timeout=None, transport=None):
        self.model = model or os.getenv("REFERRAL_MODEL", "qwen3:1.7b")
        self.base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        )
        self.timeout = float(timeout or os.getenv("INFERENCE_TIMEOUT", "120"))
        self.transport = transport
        url = urlparse(self.base_url)
        if (
            url.scheme != "http"
            or url.hostname not in ("127.0.0.1", "localhost", "::1")
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Ollama endpoint must be plain HTTP loopback without credentials/path"
            )
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:-]{0,127}", self.model)
            or "cloud" in self.model.lower()
        ):
            raise ValueError("Choose a local Ollama model identifier")

    async def readiness(self):
        """Dependency probe only: never load a model or submit a clinical note."""
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=3,
                trust_env=False,
                transport=self.transport,
            ) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                name = (
                    self.model
                    if ":" in self.model.rsplit("/", 1)[-1]
                    else self.model + ":latest"
                )
                local = next(
                    (
                        m
                        for m in response.json().get("models", [])
                        if m.get("name") == name
                    ),
                    None,
                )
                if (
                    not local
                    or local.get("remote_host")
                    or local.get("remote_model")
                    or local.get("details", {}).get("format") != "gguf"
                ):
                    raise ExtractionError("local_model_required", 503)
                return {
                    "status": "ready",
                    "model": self.model,
                    "model_digest": local.get("digest"),
                    "check": "runtime_reachable_and_local_gguf_installed",
                    "inference_verified": False,
                }
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise ExtractionError("runtime_unavailable", 503) from None

    async def extract(self, note, capture=False):
        units, user, schema = prepare(note)
        request = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": schema,
            "keep_alive": 0,
            "options": OPTIONS,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
        }
        raw = None
        try:
            async with asyncio.timeout(self.timeout):
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout,
                    trust_env=False,
                    transport=self.transport,
                ) as client:
                    tags = await client.get("/api/tags")
                    if tags.status_code != 200:
                        raise ExtractionError("runtime_unavailable", 503)
                    name = (
                        self.model
                        if ":" in self.model.rsplit("/", 1)[-1]
                        else self.model + ":latest"
                    )
                    local = next(
                        (
                            m
                            for m in tags.json().get("models", [])
                            if m.get("name") == name
                        ),
                        None,
                    )
                    if (
                        not local
                        or local.get("remote_host")
                        or local.get("remote_model")
                        or local.get("details", {}).get("format") != "gguf"
                    ):
                        raise ExtractionError("local_model_required", 503)
                    async with client.stream(
                        "POST", "/api/chat", json=request
                    ) as response:
                        if response.status_code != 200:
                            raise ExtractionError("runtime_unavailable", 503)
                        buffer = bytearray()
                        async for chunk in response.aiter_bytes():
                            buffer.extend(chunk)
                            if len(buffer) > 65536:
                                raise ExtractionError("output_limit")
                    data = json.loads(buffer)
            if not isinstance(data, dict) or not isinstance(data.get("message"), dict):
                raise ExtractionError("invalid_response")
            raw = data["message"].get("content")
            if data.get("done") is not True or data.get("done_reason") != "stop":
                raise ExtractionError("incomplete_output")
            if data.get("message", {}).get("thinking"):
                raise ExtractionError("unexpected_thinking")
            raw = data["message"]["content"]
            if not isinstance(raw, str) or len(raw.encode()) > 24000:
                raise ExtractionError("output_limit")
            fields = resolve(raw, units)
            result = {
                "fields": fields,
                "units": units,
                "model": self.model,
                "schema_version": SCHEMA["version"],
                "prompt_version": PROMPT_VERSION,
                "output_schema_version": OUTPUT_SCHEMA_VERSION,
                "segmentation_version": SEGMENTATION_VERSION,
                "model_digest": local.get("digest"),
                "settings": {"think": False, **OPTIONS},
                "metrics": {
                    k: data.get(k)
                    for k in (
                        "total_duration",
                        "load_duration",
                        "prompt_eval_count",
                        "eval_count",
                    )
                },
            }
            if capture:  # Only the explicit fictional-fixture evaluation CLI uses this.
                result["raw_output"] = raw
            return result
        except (TimeoutError, httpx.TimeoutException):
            raise ExtractionError("inference_timeout", 504) from None
        except httpx.HTTPError:
            raise ExtractionError("runtime_unavailable", 503) from None
        except (KeyError, ValueError, TypeError):
            raise ExtractionError("invalid_response") from None
        except ExtractionError as error:
            if capture:
                error.raw_output = raw
            raise
