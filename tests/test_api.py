import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.adapter import OllamaAdapter
from app.core import ExtractionError, prepare, resolve
from app.main import create_app, Gate
from tests.test_core import empty


class Fake:
    model = "mock"

    async def extract(self, note):
        await asyncio.sleep(0.01)
        units, _, _ = prepare(note)
        data = empty()
        data["history"] = [1]
        return {"fields": resolve(json.dumps(data), units), "units": units}


class Failed(Fake):
    async def extract(self, note):
        raise ExtractionError("invalid_evidence")


def test_error_distinct_and_no_content_echo():
    client = TestClient(create_app(Failed()))
    response = client.post(
        "/api/extract", json={"note": "FICTIONAL SECRET", "request_id": "1"}
    )
    assert response.status_code == 502
    assert response.json() == {"error": "invalid_evidence", "status": "failed"}
    bad = client.post(
        "/api/extract", json={"note": ["FICTIONAL SECRET"], "request_id": "1"}
    )
    assert bad.status_code == 422 and "FICTIONAL" not in bad.text


def test_limits_origin_headers_and_html_transport():
    client = TestClient(create_app(Fake()))
    assert (
        client.post(
            "/api/extract", json={"note": "x" * 3001, "request_id": "1"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/extract",
            content=b"x" * 32769,
            headers={"content-type": "application/json"},
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/extract",
            json={"note": "x", "request_id": "1"},
            headers={"origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert client.post("/api/extract", content="x").status_code == 415
    response = client.post(
        "/api/extract", json={"note": "<img src=x onerror=alert(1)>", "request_id": "1"}
    )
    assert (
        response.json()["fields"]["history"]["text"] == "<img src=x onerror=alert(1)>"
    )
    assert response.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in response.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_request_isolation():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(Fake())),
        base_url="http://testserver",
    ) as c:
        responses = await asyncio.gather(
            *[
                c.post("/api/extract", json={"note": note, "request_id": str(i)})
                for i, note in enumerate(["CASE ALPHA", "CASE BETA"])
            ]
        )
    assert [r.json()["fields"]["history"]["text"] for r in responses] == [
        "CASE ALPHA",
        "CASE BETA",
    ]


@pytest.mark.asyncio
async def test_bounded_queue_timeout_and_release():
    gate = Gate(waiting=1, wait_seconds=0.02)
    async with gate.enter():

        async def queued():
            with pytest.raises(ExtractionError) as e:
                async with gate.enter():
                    pass
            assert e.value.code == "queue_timeout"

        task = asyncio.create_task(queued())
        await asyncio.sleep(0.005)
        with pytest.raises(ExtractionError) as e:
            async with gate.enter():
                pass
        assert e.value.code == "queue_full"
        await task
    assert gate.count == 0
    async with gate.enter():
        assert gate.count == 1


def transport_with(data=None, delay=0):
    async def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen3:1.7b",
                            "details": {"format": "gguf"},
                            "digest": "test",
                        }
                    ]
                },
            )
        body = json.loads(request.content)
        assert body["think"] is False and body["stream"] is False
        assert body["format"]["additionalProperties"] is False
        await asyncio.sleep(delay)
        return httpx.Response(200, json=data)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_adapter_timeout():
    adapter = OllamaAdapter(timeout=0.01, transport=transport_with(delay=0.1))
    with pytest.raises(ExtractionError) as e:
        await adapter.extract("Халуураагүй.")
    assert e.value.code == "inference_timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "done,reason,thinking,expected",
    [
        (False, "stop", "", "incomplete_output"),
        (True, "length", "", "incomplete_output"),
        (True, "stop", "reasoning", "unexpected_thinking"),
    ],
)
async def test_partial_and_thinking_rejected(done, reason, thinking, expected):
    adapter = OllamaAdapter(
        transport=transport_with(
            {
                "done": done,
                "done_reason": reason,
                "message": {"content": json.dumps(empty()), "thinking": thinking},
            }
        )
    )
    with pytest.raises(ExtractionError) as e:
        await adapter.extract("Халуураагүй.")
    assert e.value.code == expected


@pytest.mark.asyncio
async def test_valid_abstention_not_failure():
    adapter = OllamaAdapter(
        transport=transport_with(
            {
                "done": True,
                "done_reason": "stop",
                "message": {"content": json.dumps(empty())},
            }
        )
    )
    result = await adapter.extract("Халуураагүй.")
    assert all(v["status"] == "not_found" for v in result["fields"].values())


@pytest.mark.asyncio
async def test_nonexistent_local_model_rejected():
    adapter = OllamaAdapter(model="soum-tuned:latest", transport=transport_with())
    with pytest.raises(ExtractionError) as e:
        await adapter.extract("x")
    assert e.value.code == "local_model_required"


def test_remote_runtime_rejected():
    with pytest.raises(ValueError):
        OllamaAdapter(base_url="https://example.com")


@pytest.mark.asyncio
async def test_output_limit_and_invalid_envelope():
    for data, expected in [
        (None, "invalid_response"),
        ([], "invalid_response"),
        (
            {"done": True, "done_reason": "stop", "message": {"content": "x" * 70000}},
            "output_limit",
        ),
    ]:
        adapter = OllamaAdapter(transport=transport_with(data))
        with pytest.raises(ExtractionError) as e:
            await adapter.extract("x")
        assert e.value.code == expected


@pytest.mark.asyncio
async def test_queue_cancel_releases_waiter():
    gate = Gate(waiting=1)
    async with gate.enter():

        async def wait():
            async with gate.enter():
                pass

        task = asyncio.create_task(wait())
        await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert gate.count == 1
    assert gate.count == 0


@pytest.mark.parametrize("mode", ["local", "hosted"])
def test_deployment_mode_configuration(monkeypatch, mode):
    monkeypatch.setenv("DEPLOYMENT_MODE", mode)
    config = TestClient(create_app(Fake())).get("/api/config").json()
    assert config["deployment_mode"] == mode


def test_deployment_mode_defaults_local_and_rejects_typos(monkeypatch):
    monkeypatch.delenv("DEPLOYMENT_MODE", raising=False)
    assert (
        TestClient(create_app(Fake())).get("/api/config").json()["deployment_mode"]
        == "local"
    )
    monkeypatch.setenv("DEPLOYMENT_MODE", "hostedd")
    with pytest.raises(ValueError, match="DEPLOYMENT_MODE"):
        create_app(Fake())


def test_v07_form_version_is_separate_from_unchanged_extraction_contract():
    config = TestClient(create_app(Fake())).get("/api/config").json()
    assert config["version"] == "experimental-0.7"
    assert config["extraction_schema_version"] == "experimental-0.6"
    assert config["prompt_version"] == "source-id-v06-1"
    assert len(config["proposal_mapping"]) == 19
