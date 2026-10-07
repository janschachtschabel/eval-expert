import asyncio
import json

import pytest

from app.run_store import enqueue, save_result, snapshot
from app.runner import execute_run


def test_large_csv_cells_follow_the_documented_upload_limit(team_client):
    client, headers = team_client
    response = client.post(
        "/api/catalog/datasets",
        headers=headers,
        json={
            "name": "Large cell",
            "format": "csv",
            "content": "id,description\n1," + "x" * 150000 + "\n",
        },
    )
    assert response.status_code == 200


def test_lists_are_small_and_paginate_older_history(team_client):
    client, headers = team_client
    plan = client.post("/api/demo", headers=headers).json()["plan_id"]
    db = client.app.state.db
    saved = snapshot(db, plan)
    saved["dataset"]["cases"] = [{"id": "1", "input": {"text": "x" * 100000}, "reference": {}}]
    for _ in range(205):
        id = enqueue(db, saved)
        with db.connect() as c:
            c.execute("UPDATE runs SET status='completed' WHERE id=?", (id,))
    first = client.get("/api/runs/page?limit=50").json()
    last = client.get("/api/runs/page?limit=50&offset=200").json()
    assert first["total"] == 205 and len(first["items"]) == 50 and len(last["items"]) == 5
    assert len(json.dumps(first)) < 100000
    datasets = client.get("/api/catalog/datasets").json()
    assert "cases" not in datasets[0]
    assert datasets[0]["case_count"] == 12
    assert len(client.get("/api/catalog/datasets/" + datasets[0]["id"]).json()["cases"]) == 12
    detail = client.get("/api/runs/" + id).json()
    assert "cases" not in detail["snapshot"]["dataset"]


def test_case_pages_and_full_exports_have_distinct_contracts(team_client):
    client, headers = team_client
    plan = client.post("/api/demo", headers=headers).json()["plan_id"]
    db = client.app.state.db
    saved = snapshot(db, plan)
    saved["dataset"]["cases"] = [{"id": str(i), "input": {}, "reference": {}} for i in range(60)]
    id = enqueue(db, saved)
    asyncio.run(execute_run(client.app, id))
    page = client.get(f"/api/runs/{id}/cases?limit=25&offset=50").json()
    assert page["total"] == 60 and len(page["items"]) == 10
    assert len(client.get(f"/api/runs/{id}").json()["results"]) <= 25
    assert client.get(f"/api/runs/{id}/status").json()["progress"] == 60
    assert "results" not in client.get(f"/api/runs/{id}/status").json()
    assert len(client.get(f"/api/runs/{id}/export").json()["results"]) == 60


def test_run_evidence_budget_is_atomic(team_client):
    client, headers = team_client
    plan = client.post("/api/demo", headers=headers).json()["plan_id"]
    db = client.app.state.db
    id = enqueue(db, snapshot(db, plan))
    with pytest.raises(ValueError, match="evidence budget"):
        save_result(db, id, 0, {"large": "x" * 300}, max_bytes=100)
    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM results WHERE run_id=?", (id,)).fetchone()[0] == 0
