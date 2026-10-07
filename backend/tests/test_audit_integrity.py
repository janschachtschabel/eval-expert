import pytest

from app.run_store import enqueue, snapshot
from app.scheduler import tick


def test_full_queue_keeps_a_schedule_due_until_capacity_returns(team_client):
    client, headers = team_client
    plan = client.post("/api/demo", headers=headers).json()["plan_id"]
    db = client.app.state.db
    saved = snapshot(db, plan)
    for _ in range(20):
        enqueue(db, saved)
    schedule = db.save_catalog(
        "schedules",
        {
            "name": "Due",
            "plan_id": plan,
            "enabled": True,
            "cron": "0 8 * * *",
            "timezone": "Europe/Berlin",
        },
    )
    due = "2026-01-01T00:00:00+00:00"
    with db.connect() as c:
        c.execute("INSERT INTO schedule_state VALUES(?,?)", (schedule["id"], due))
    tick(db)
    with db.connect() as c:
        assert c.execute("SELECT next_due FROM schedule_state").fetchone()[0] == due
        c.execute("UPDATE runs SET status='completed'")
    tick(db)
    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 21
        assert c.execute("SELECT next_due FROM schedule_state").fetchone()[0] != due


def test_stale_update_returns_conflict_and_preserves_first_change(team_client):
    client, headers = team_client
    original = client.post(
        "/api/catalog/criteria",
        headers=headers,
        json={"name": "Criterion", "steps": ["Judge clarity."]},
    ).json()
    path = "/api/catalog/criteria/" + original["id"]
    assert (
        client.put(
            path, headers=headers, json={**original, "description": "First editor"}
        ).status_code
        == 200
    )
    assert (
        client.put(path, headers=headers, json={**original, "name": "Second editor"}).status_code
        == 409
    )
    assert client.get(path).json()["description"] == "First editor"
    assert (
        client.put(
            path, headers=headers, json={"name": "Missing version", "steps": ["Judge clarity."]}
        ).status_code
        == 422
    )


def test_used_resources_cannot_be_deleted_and_bad_references_are_rejected(team_client):
    client, headers = team_client
    plan_id = client.post("/api/demo", headers=headers).json()["plan_id"]
    plan = client.get("/api/catalog/plans/" + plan_id).json()
    assert (
        client.delete("/api/catalog/services/" + plan["service_id"], headers=headers).status_code
        == 409
    )
    assert (
        client.post(
            "/api/catalog/plans", headers=headers, json={**plan, "service_id": "missing"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/catalog/schedules", headers=headers, json={"name": "Bad", "plan_id": "missing"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "url,body,status",
    [
        (
            "/api/catalog/datasets",
            {
                "name": "Short CSV",
                "format": "csv",
                "content": "id,title,reference.subject\n1,Title\n",
            },
            422,
        ),
        ("/api/connections/schedule-preview", {"cron": "0 8 * * *", "timezone": []}, 422),
        ("/api/runs/missing/recompute", {}, 404),
        ("/api/runs", {"plan_id": []}, 422),
    ],
)
def test_malformed_requests_have_a_client_error_contract(team_client, url, body, status):
    client, headers = team_client
    assert client.post(url, headers=headers, json=body).status_code == status
