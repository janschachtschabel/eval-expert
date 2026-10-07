import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.runner import execute_run, recover
from app.scheduler import next_due


def test_schedule_uses_berlin_dst():
    config = {"cron": "0 8 * * 1", "timezone": "Europe/Berlin"}
    assert (
        next_due(config, datetime.fromisoformat("2026-10-23T12:00:00+00:00"))
        == "2026-10-26T07:00:00+00:00"
    )


def test_invalid_timezone_is_a_configuration_error():
    with pytest.raises(ValueError, match="time zone"):
        next_due({"cron": "0 8 * * 1", "timezone": "not/a-zone"})


def test_spring_schedule_uses_berlin_dst():
    config = {"cron": "0 8 * * 1", "timezone": "Europe/Berlin"}
    assert (
        next_due(config, datetime.fromisoformat("2026-03-27T12:00:00+00:00"))
        == "2026-03-30T06:00:00+00:00"
    )


def test_snapshot_recompute_and_recovery(tmp_path):
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            secret_key="a" * 40,
            admin_password="Strong-initial-password!",
            secure_cookie=False,
        ),
        start_worker=False,
    )
    with TestClient(app) as c:
        token = c.post(
            "/api/auth/login", json={"username": "admin", "password": "Strong-initial-password!"}
        ).json()["csrf_token"]
        headers = {"X-CSRF-Token": token}
        demo = c.post("/api/demo", headers=headers).json()
        run = c.post("/api/runs", headers=headers, json={"plan_id": demo["plan_id"]}).json()
        asyncio.run(execute_run(app, run["id"]))
        complete = c.get(f"/api/runs/{run['id']}").json()
        assert complete["status"] == "completed"
        assert complete["summary"]["target_success_rate"] == 1
        assert complete["summary"]["reference"][0]["micro"]["f1"] < 1
        assert complete["snapshot"]["dataset"]["demo"] is True
        assert "_secret" not in complete["snapshot"]["service"]
        replay = c.post(f"/api/runs/{run['id']}/recompute", headers=headers).json()
        asyncio.run(execute_run(app, replay["id"]))
        result = c.get(f"/api/runs/{replay['id']}").json()
        assert result["summary"]["reference"] == complete["summary"]["reference"]
        assert all(row["reused_response"] for row in result["results"])
        interrupted = c.post("/api/runs", headers=headers, json={"plan_id": demo["plan_id"]}).json()
        with app.state.db.connect() as connection:
            connection.execute("UPDATE runs SET status='running' WHERE id=?", (interrupted["id"],))
        recover(app.state.db)
        assert c.get(f"/api/runs/{interrupted['id']}").json()["status"] == "interrupted"
        exported = c.get(f"/api/runs/{run['id']}/export?format=csv")
        assert exported.status_code == 200 and "case_id" in exported.text
        assert c.get(f"/api/runs/{run['id']}/report").status_code == 200
