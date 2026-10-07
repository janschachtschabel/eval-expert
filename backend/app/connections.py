from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import administrators, editors
from .models import SchedulePreview
from .runner import decrypted, safe_error
from .target import call_target, request_json, validate_url

router = APIRouter(prefix="/connections")


@router.post("/schedule-preview")
def schedule_preview(body: SchedulePreview, user=Depends(editors)):
    from datetime import datetime

    from .scheduler import next_due

    try:
        dates, after = [], None
        for _ in range(5):
            value = next_due(body.model_dump(), after)
            dates.append(value)
            after = datetime.fromisoformat(value)
        return {"dates": dates}
    except (KeyError, ValueError) as error:
        raise HTTPException(422, "Invalid cron expression or time zone.") from error


@router.post("/openapi")
async def openapi(body: dict, request: Request, user=Depends(administrators)):
    url = body.get("url", "")
    try:
        spec = await request_json(url, request.app.state.settings)
        if not isinstance(spec, dict) or not str(spec.get("openapi", "")).startswith("3."):
            raise ValueError("Expected an OpenAPI 3.x document.")
        base = urljoin(url, spec.get("servers", [{"url": "/"}])[0]["url"])
        # Spec-provided server URLs cannot escape the configured network policy.
        validate_url(base, request.app.state.settings)
        operations = []
        for path, methods in spec.get("paths", {}).items():
            for method, operation in methods.items():
                if method not in ("get", "post", "put", "patch"):
                    continue
                if "{" in path:
                    continue
                schema = (
                    operation.get("requestBody", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                operations.append(
                    {
                        "method": method.upper(),
                        "url": base.rstrip("/") + path,
                        "name": operation.get("summary") or operation.get("operationId") or path,
                        "input_schema": schema,
                        "parameters": operation.get("parameters", []),
                    }
                )
        return {
            "title": spec.get("info", {}).get("title", "API"),
            "operations": operations,
            "schemas": spec.get("components", {}).get("schemas", {}),
        }
    except Exception as error:
        raise HTTPException(422, safe_error(error)) from error


@router.post("/preview")
async def preview(body: dict, request: Request, user=Depends(administrators)):
    try:
        service = request.app.state.db.get_catalog("services", body["service_id"], True)
        output = await call_target(
            service,
            body["input"],
            request.app.state.settings,
            decrypted(service, request.app.state.settings),
        )
        return {"output": output}
    except Exception as error:
        raise HTTPException(422, safe_error(error)) from error


@router.post("/models")
async def models(body: dict, request: Request, user=Depends(administrators)):
    try:
        provider = request.app.state.db.get_catalog("providers", body["provider_id"], True)
        key = decrypted(provider, request.app.state.settings)
        base = provider["base_url"].rstrip("/")
        if provider["kind"].startswith("bapi-"):
            url = f"{base}/api/v1/llm/{provider['kind'].removeprefix('bapi-')}/models"
            headers = {"X-API-KEY": key}
        else:
            url, headers = f"{base}/models", {"Authorization": f"Bearer {key}"}
        return await request_json(url, request.app.state.settings, headers=headers)
    except Exception as error:
        raise HTTPException(422, safe_error(error)) from error
