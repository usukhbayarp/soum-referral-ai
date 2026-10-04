import asyncio
import os
import json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .adapter import OllamaAdapter
from .core import (
    ExtractionError,
    MAX_CHARS,
    SCHEMA,
    ROOT,
    PROMPT_VERSION,
    OUTPUT_SCHEMA_VERSION,
    SEGMENTATION_VERSION,
)

STATIC = Path(__file__).parent / "static"


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    note: str = Field(min_length=1, max_length=MAX_CHARS)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")


class Gate:
    """Single-process bound: one active inference and at most two waiting requests."""

    def __init__(self, waiting=2, wait_seconds=15):
        self.capacity = waiting + 1
        self.count = 0
        self.slot = asyncio.Semaphore(1)
        self.wait_seconds = wait_seconds

    @asynccontextmanager
    async def enter(self):
        # No await between check and increment: atomic within this event loop.
        if self.count >= self.capacity:
            raise ExtractionError("queue_full", 429)
        self.count += 1
        acquired = False
        try:
            try:
                await asyncio.wait_for(self.slot.acquire(), self.wait_seconds)
                acquired = True
            except TimeoutError:
                raise ExtractionError("queue_timeout", 503) from None
            yield
        finally:
            if acquired:
                self.slot.release()
            self.count -= 1


class RequestBoundary:
    """Bound bytes before JSON parsing; no raw body in error responses/logs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        if scope["method"] == "POST":
            origin = headers.get(b"origin", b"").decode()
            host = headers.get(b"host", b"").decode()
            if origin and origin not in (f"http://{host}", f"https://{host}"):
                return await JSONResponse({"error": "origin_rejected"}, 403)(
                    scope, receive, send
                )
            if headers.get(b"content-type", b"").split(b";")[0] != b"application/json":
                return await JSONResponse({"error": "json_required"}, 415)(
                    scope, receive, send
                )
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > 32768:
                            return await JSONResponse({"error": "input_limit"}, 413)(
                                scope, receive, send
                            )
                        if not message.get("more_body"):
                            break
            except TimeoutError:
                return await JSONResponse({"error": "request_timeout"}, 408)(
                    scope, receive, send
                )
            consumed = False

            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {
                        "type": "http.request",
                        "body": bytes(body),
                        "more_body": False,
                    }
                return await receive()

            return await self.app(scope, replay, send)
        return await self.app(scope, receive, send)


def create_app(adapter=None, gate=None):
    deployment_mode = os.getenv("DEPLOYMENT_MODE", "local")
    if deployment_mode not in ("local", "hosted"):
        raise ValueError("DEPLOYMENT_MODE must be local or hosted")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.adapter = adapter or OllamaAdapter()
    app.state.gate = gate or Gate()
    app.add_middleware(RequestBoundary)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv(
            "APP_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1],testserver"
        ).split(","),
    )

    @app.middleware("http")
    async def privacy_headers(request, call_next):
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {"error": "invalid_request", "status": "failed"}, status_code=422
        )

    @app.exception_handler(ExtractionError)
    async def extraction_error(request, exc):
        return JSONResponse(
            {"error": exc.code, "status": "failed"}, status_code=exc.status
        )

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/config")
    async def config():
        return {
            **SCHEMA,
            "model": app.state.adapter.model,
            "prompt_version": PROMPT_VERSION,
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "segmentation_version": SEGMENTATION_VERSION,
            "max_chars": MAX_CHARS,
            "deployment_mode": deployment_mode,
            "inference_timeout": (
                app.state.adapter.timeout
                if hasattr(app.state.adapter, "timeout")
                else 120
            ),
        }

    @app.get("/api/example/dev002")
    async def example():
        case = json.loads((ROOT / "evaluation/dev002-v06/cases.json").read_text())[0]
        return {
            k: case[k]
            for k in (
                "case_id",
                "source_note",
                "schema_version",
                "clinician_review_status",
                "split",
            )
        }

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "model": app.state.adapter.model}

    @app.get("/api/ready")
    async def ready():
        return await app.state.adapter.readiness()

    @app.post("/api/extract")
    async def extract(payload: ExtractRequest):
        async with app.state.gate.enter():
            result = await app.state.adapter.extract(payload.note)
        return {**result, "request_id": payload.request_id}

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
