import asyncio
import io
import json

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.judge import JudgeModel, evaluate
from app.target import call_target, request_json, validate_url


def test_network_policy_and_mappings():
    settings = Settings(allowed_hosts="metadata.example.org")
    assert validate_url("https://metadata.example.org/classify", settings)
    for url in (
        "http://127.0.0.1/",
        "http://169.254.169.254/",
        "file:///etc/passwd",
        "https://user:secret@metadata.example.org/",
        "https://unlisted.example.org/",
    ):
        with pytest.raises(ValueError):
            validate_url(url, settings)


@pytest.mark.asyncio
async def test_target_never_receives_reference_and_does_not_follow_redirects():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(302, headers={"location": "http://unlisted.example.org"})

    service = {
        "kind": "http",
        "url": "https://metadata.example.org/test",
        "method": "POST",
        "mapping": {"title": {"$input": "/title"}},
        "headers": {},
        "timeout": 10,
    }
    with pytest.raises(ValueError, match="302"):
        await call_target(
            service,
            {"title": "A"},
            Settings(allowed_hosts="metadata.example.org"),
            transport=httpx.MockTransport(handler),
        )
    assert requests == [{"title": "A"}]


class Score(BaseModel):
    score: int
    reason: str


@pytest.mark.asyncio
@pytest.mark.parametrize("context_source", ["input", "output"])
async def test_bapi_schema_and_actual_deepeval_metric(context_source):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"score":8,"reason":"Clear description, '
                            'supported by the source."}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            },
        )

    provider = {
        "name": "Test",
        "kind": "bapi-academiccloud",
        "base_url": "https://b-api.prod.openeduhub.net",
        "model": "test-model",
        "max_tokens": 1024,
        "token_parameter": "max_tokens",
        "temperature": None,
    }
    model = JudgeModel(provider, "secret", Settings(), httpx.MockTransport(handler))
    result = await evaluate(
        model,
        {
            "name": "Clarity",
            "steps": ["Assess clarity from 0 to 10."],
            "threshold": 0.7,
            "output_path": "/description",
            "context_path": "/source",
            "context_source": context_source,
        },
        {"title": "A", "source": "A source"},
        {"description": "A description", "source": "Original webpage evidence"},
    )
    assert result["score"] == 0.8
    assert result["passed"] is True
    assert result["source_supplied"] is True
    assert "secret" not in json.dumps(result["calls"])
    assert result["usage"]["completion_tokens"] == 30
    assert seen[0].headers["x-api-key"] == "secret"
    assert "authorization" not in seen[0].headers
    payload = json.loads(seen[0].content)
    assert "max_tokens" in payload and "temperature" not in payload
    assert seen[0].url.path == "/api/v1/llm/academiccloud/chat/completions"


@pytest.mark.asyncio
async def test_reasoning_only_is_judge_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": None, "reasoning": "thinking"}}]}
        )
    )
    model = JudgeModel(
        {
            "name": "test",
            "kind": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "x",
            "max_tokens": 1024,
        },
        "secret",
        Settings(),
        transport,
    )
    with pytest.raises(ValueError, match="content"):
        await model.a_generate("Judge", schema=Score)


@pytest.mark.asyncio
async def test_remote_schema_reference_cannot_bypass_network_policy(monkeypatch):
    seen = []

    def remote(url):
        seen.append(url)
        return io.BytesIO(b'{"type":"object"}')

    monkeypatch.setattr("urllib.request.urlopen", remote)
    service = {
        "kind": "http",
        "url": "https://metadata.example.org/test",
        "method": "POST",
        "mapping": {"$input": ""},
        "response_schema": {"$ref": "http://169.254.169.254/schema"},
    }
    with pytest.raises(ValueError, match="local"):
        await call_target(
            service,
            {},
            Settings(allowed_hosts="metadata.example.org"),
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        )
    assert seen == []


@pytest.mark.asyncio
async def test_required_source_blocks_unsubstantiated_judgment():
    model = JudgeModel(
        {"kind": "openai", "base_url": "https://api.openai.com/v1", "model": "test"},
        "secret",
        Settings(),
        httpx.MockTransport(lambda request: httpx.Response(401)),
    )
    with pytest.raises(ValueError, match="source"):
        await evaluate(
            model,
            {
                "name": "Advertising",
                "steps": ["Check source for advertising."],
                "threshold": 0.7,
                "output_path": "/description",
                "require_context": True,
            },
            {"source": "   "},
            {"description": "A neutral description."},
        )
    assert model.usage["requests"] == 0


@pytest.mark.asyncio
async def test_total_request_deadline_limits_slow_streams():
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{"
            await asyncio.sleep(0.1)
            yield b"}"

    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowStream()))
    with pytest.raises(TimeoutError):
        await request_json(
            "https://metadata.example.org",
            Settings(allowed_hosts="metadata.example.org"),
            timeout=0.02,
            transport=transport,
        )
