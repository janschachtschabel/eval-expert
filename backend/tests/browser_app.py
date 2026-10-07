"""Isolated browser-test factory: mock external HTTP, keep the real app and worker."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.main import create_app

original_client = httpx.AsyncClient


async def remote(request):
    path = request.url.path
    if request.url.host == "metadata.example.org":
        if path == "/openapi.json":
            return httpx.Response(
                200,
                json={
                    "openapi": "3.1.0",
                    "info": {"title": "Browser extractor"},
                    "servers": [{"url": "https://metadata.example.org"}],
                    "paths": {
                        "/from-url": {
                            "post": {
                                "summary": "Extract URL",
                                "requestBody": {
                                    "content": {"application/json": {"schema": {"type": "object"}}}
                                },
                            }
                        }
                    },
                },
            )
        if path == "/empty-openapi.json":
            return httpx.Response(200, json={"openapi": "3.1.0", "paths": {}})
        if path == "/from-url":
            body = json.loads(request.content)
            if "slow" in body.get("url", ""):
                await asyncio.sleep(1)
            if "failure" in body.get("url", ""):
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "text": "Sachlicher Lerntext: Bruchrechnung ohne Werbung.",
                    "subject": ["math"],
                    "status": 200,
                    "version": "browser-fixture",
                },
            )
    if path.endswith("/models"):
        return httpx.Response(200, json={"data": [{"id": "browser-judge-model"}]})
    if path.endswith("/chat/completions"):
        is_openai = request.url.host == "api.openai.com" and path == "/v1/chat/completions"
        is_bapi = request.url.host == "b-api.prod.openeduhub.net" and path in {
            "/api/v1/llm/openai/chat/completions",
            "/api/v1/llm/academiccloud/chat/completions",
        }
        credential = request.headers.get("authorization" if is_openai else "x-api-key")
        if not (is_openai or is_bapi) or credential != (
            "Bearer disposable-browser-key" if is_openai else "disposable-browser-key"
        ):
            return httpx.Response(401)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "score": 9,
                                    "reason": "Sachlicher Lerntext ohne Werbeaufforderung.",
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 400, "completion_tokens": 150},
            },
        )
    return httpx.Response(503)


def create_test_app():
    settings = Settings()
    settings.allowed_hosts = "metadata.example.org"

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(remote)
        return original_client(*args, **kwargs)

    httpx.AsyncClient = client
    return create_app(settings)
