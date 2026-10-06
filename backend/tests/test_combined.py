import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.runner import execute_run


def test_generic_combined_run_calls_target_once_and_records_judge_protocol(tmp_path, monkeypatch):
    seen = []

    def remote(request):
        seen.append(request)
        if request.url.host == "metadata.example.org":
            assert json.loads(request.content) == {"text": "Brüche"}
            return httpx.Response(
                200,
                json={
                    "metadata": {"subjects": ["math"]},
                    "description": "Eine sachliche Einführung.",
                    "source": "Bruchrechnung für die Schule.",
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"score":9,"reason":"Clear and source-based."}'}}
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 20},
            },
        )

    original = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(remote)
        return original(*args, **kwargs)

    monkeypatch.setattr("app.target.httpx.AsyncClient", client_factory)
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            secret_key="a" * 40,
            admin_password="Strong-password!",
            secure_cookie=False,
            allowed_hosts="metadata.example.org",
        ),
        start_worker=False,
    )
    with TestClient(app) as c:
        session = c.post(
            "/api/auth/login", json={"username": "admin", "password": "Strong-password!"}
        ).json()
        headers = {"X-CSRF-Token": session["csrf_token"]}

        def save(kind, body):
            response = c.post("/api/catalog/" + kind, headers=headers, json=body)
            assert response.status_code == 200
            return response.json()["id"]

        service = save(
            "services",
            {
                "name": "HTTP API",
                "url": "https://metadata.example.org/classify",
                "mapping": {"text": {"$input": "/title"}},
            },
        )
        dataset = save(
            "datasets",
            {
                "name": "Gold",
                "cases": [
                    {"id": "one", "input": {"title": "Brüche"}, "reference": {"subject": ["math"]}}
                ],
            },
        )
        provider = save("providers", {"name": "OpenAI", "model": "test", "api_key": "private-key"})
        criterion = save(
            "criteria",
            {
                "name": "Description",
                "steps": ["Judge source-based clarity."],
                "output_path": "/description",
                "context_path": "/source",
                "context_source": "output",
            },
        )
        plan = save(
            "plans",
            {
                "name": "Combined",
                "mode": "combined",
                "service_id": service,
                "dataset_id": dataset,
                "provider_id": provider,
                "criterion_ids": [criterion],
                "fields": [
                    {
                        "name": "subject",
                        "output_path": "/metadata/subjects",
                        "reference_path": "/subject",
                    }
                ],
            },
        )
        id = c.post("/api/runs", headers=headers, json={"plan_id": plan}).json()["id"]
        asyncio.run(execute_run(app, id))
        result = c.get("/api/runs/" + id).json()
        assert result["summary"]["reference"][0]["micro"]["f1"] == 1
        assert result["summary"]["judge"]["mean_score"] == 0.9
        assert len([r for r in seen if r.url.host == "metadata.example.org"]) == 1
        assert len(seen) == 2
        assert result["results"][0]["judges"][0]["source_supplied"] is True
        assert "private-key" not in json.dumps(result)
