import asyncio
import ipaddress
import json
from urllib.parse import urlsplit

import httpx
from jsonschema import ValidationError, validate
from referencing import Registry

from .pointers import render_mapping
from .schemas import check_schema

DEFAULT_HOSTS = {"api.openai.com", "b-api.prod.openeduhub.net", "b-api.staging.openeduhub.net"}


class ResponseValidationError(ValueError):
    def __init__(self, output):
        super().__init__("Response does not match the configured JSON schema.")
        self.output = output


def validate_url(url, settings):
    parsed = urlsplit(url)
    allowed = DEFAULT_HOSTS | {
        host.strip().lower() for host in settings.allowed_hosts.split(",") if host.strip()
    }
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ValueError("Use an HTTP(S) endpoint.")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Credentials and fragments are not allowed in endpoint URLs.")
    if parsed.hostname.lower() not in allowed:
        raise ValueError(f"Host {parsed.hostname} is not in EVAL_ALLOWED_HOSTS.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
        if address.is_link_local or address.is_multicast or address.is_unspecified:
            raise ValueError("Link-local, multicast and unspecified addresses are prohibited.")
    except ValueError as error:
        if "prohibited" in str(error):
            raise
    return url


async def request_json(
    url, settings, method="GET", body=None, headers=None, timeout=60, transport=None
):
    validate_url(url, settings)
    async with (
        asyncio.timeout(timeout),
        httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, trust_env=False, transport=transport
        ) as client,
    ):
        kwargs = {"headers": headers or {}}
        if body is not None:
            kwargs["params" if method == "GET" else "json"] = body
        async with client.stream(method, url, **kwargs) as response:
            if not 200 <= response.status_code < 300:
                raise ValueError(f"Remote service returned HTTP {response.status_code}.")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError("Remote response exceeds 2 MB.")
                chunks.append(chunk)
    try:
        return json.loads(b"".join(chunks))
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Remote response is not valid JSON.") from error


async def call_target(service, input, settings, key="", transport=None):
    if service["kind"] == "demo":
        return demo_output(input)
    mapped = render_mapping(service["mapping"], input)
    headers = dict(service.get("headers", {}))
    if key:
        headers[service.get("auth_header", "Authorization")] = (
            service.get("auth_prefix", "Bearer ") + key
        )
    output = await request_json(
        service["url"],
        settings,
        service["method"],
        mapped,
        headers,
        service.get("timeout", 60),
        transport,
    )
    if service.get("response_schema"):
        check_schema(service["response_schema"])
        # Explicit empty registry prevents implicit, unbounded HTTP retrieval of $ref schemas.
        try:
            validate(output, service["response_schema"], registry=Registry())
        except ValidationError as error:
            raise ResponseValidationError(output) from error
    return output


def demo_output(input):
    """A local deterministic classifier, with deliberately imperfect predictions."""
    text = (input.get("title", "") + " " + input.get("description", "")).lower()
    subject = []
    for token, label in [
        ("bruch", "math"),
        ("geometr", "math"),
        ("energie", "physics"),
        ("strom", "physics"),
        ("pflanz", "biology"),
        ("zelle", "biology"),
        ("geschichte", "history"),
        ("gedicht", "german"),
    ]:
        if token in text:
            subject.append(label)
    return {
        "title": input.get("title", ""),
        "description": input.get("description", ""),
        "subject": sorted(set(subject)),
        "educational_level": ["secondary"],
        "keywords": input.get("keywords", []),
    }
