import asyncio, json, time
from pathlib import Path
import httpx
from app.adapter import OllamaAdapter
from app.core import ExtractionError

D = Path("evaluation/recovery-v06")
D.mkdir(exist_ok=True)


class Trace(httpx.AsyncBaseTransport):
    def __init__(self):
        self.inner = httpx.AsyncHTTPTransport()
        self.calls = []

    async def handle_async_request(self, r):
        response = await self.inner.handle_async_request(r)
        if r.url.path == "/api/chat":
            body = await response.aread()
            self.calls.append(
                {
                    "serialized_request": r.content.decode(),
                    "status": response.status_code,
                    "response": json.loads(body),
                }
            )
        return response

    async def aclose(self):
        await self.inner.aclose()


async def main():
    if (D / "baseline-4b-dev002.json").exists():
        raise FileExistsError(
            "Preserve existing capture; use a fresh checkout/output path"
        )
    case = json.loads(Path("evaluation/dev002-v06/cases.json").read_text())[0]
    t = Trace()
    a = OllamaAdapter(model="qwen3:4b", transport=t)
    start = time.perf_counter()
    out = {}
    async with httpx.AsyncClient(trust_env=False) as c:
        out["identity"] = (
            await c.post(a.base_url + "/api/show", json={"model": a.model})
        ).json()
        out["tags"] = (await c.get(a.base_url + "/api/tags")).json()
    try:
        out["output"] = await a.extract(case["source_note"], capture=True)
        out["error"] = None
    except ExtractionError as e:
        out["error"] = e.code
    out.update(
        case_id=case["case_id"],
        latency_seconds=time.perf_counter() - start,
        calls=t.calls,
    )
    (D / "baseline-4b-dev002.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(out["error"], out["latency_seconds"], flush=True)


asyncio.run(main())
