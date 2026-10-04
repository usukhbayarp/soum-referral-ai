"""One tiny non-thinking smoke; never alters existing tags or serving defaults."""

import json, time, httpx, hashlib
from scripts.original4b_comparison import OUT, TAG


def main():
    target = OUT / "smoke.json"
    if target.exists():
        raise FileExistsError(target)
    with httpx.Client(
        base_url="http://127.0.0.1:11434", trust_env=False, timeout=60
    ) as c:
        show = c.post("/api/show", json={"model": TAG})
        show.raise_for_status()
        identity = show.json()
        template = identity["template"]
        pins = json.loads((OUT.parent.parent / "training/pins.json").read_text())
        assert (
            hashlib.sha256(template.encode()).hexdigest()
            == pins["serving_template_sha256"]
        )
        assert ".Think" in template and "/no_think" in template
        assert identity["model_info"]["general.architecture"] == "qwen3"
        request = {
            "model": TAG,
            "messages": [{"role": "user", "content": 'Return exactly {"ok":true}.'}],
            "format": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
            "think": False,
            "stream": False,
            "keep_alive": 0,
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_ctx": 16384,
                "num_predict": 32,
            },
        }
        report = {
            "identity": identity,
            "request": request,
            "loaded_before": c.get("/api/ps").json(),
            "note": "keep_alive=0 unloads only this newly imported smoke model to make first comparison cold. Existing models untouched.",
        }
        wire = c.build_request("POST", "/api/chat", json=request)
        report["serialized_request"] = wire.content.decode()
        start = time.perf_counter()
        try:
            response = c.send(wire)
            report["raw_response"] = response.text
            response.raise_for_status()
            j = response.json()
            report["response"] = j
            report["pass"] = (
                j.get("done") is True
                and j.get("done_reason") == "stop"
                and not j.get("message", {}).get("thinking")
                and json.loads(j["message"]["content"]) == {"ok": True}
            )
        except Exception as e:
            report["error"] = str(e)
            report["pass"] = False
        report["wall_seconds"] = time.perf_counter() - start
        report["loaded_after"] = c.get("/api/ps").json()
        target.write_text(json.dumps(report, indent=2))
        print("Smoke", report["pass"], report["wall_seconds"])
        assert report["pass"]


if __name__ == "__main__":
    main()
