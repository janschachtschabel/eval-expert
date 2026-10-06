from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from app.auth import cipher
from app.config import Settings
from app.database import Database
from app.judge import JudgeModel, evaluate
from app.main import create_app
from app.models import Plan
from app.run_store import comparison_key, enqueue, read_run
from app.runner import execute_run
from app.scheduler import tick


@pytest.mark.asyncio
async def test_out_of_range_judge_score_is_rejected():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"score":20,"reason":"Invalid scale"}'}}]},
        )
    )
    model = JudgeModel(
        {"kind": "openai", "base_url": "https://api.openai.com/v1", "model": "x"},
        "secret",
        Settings(),
        transport,
    )
    with pytest.raises(ValueError, match="score"):
        await evaluate(
            model, {"name": "Clarity", "steps": ["Assess clarity."], "threshold": 0.7}, {}, {}
        )


def test_duplicate_schedule_key_after_restart_advances_schedule(tmp_path, monkeypatch):
    db = Database(tmp_path)
    schedule = db.save_catalog(
        "schedules",
        {
            "name": "Test",
            "plan_id": "p",
            "cron": "0 8 * * 1",
            "timezone": "Europe/Berlin",
            "enabled": True,
        },
    )
    due = "2026-01-01T00:00:00+00:00"
    with db.connect() as connection:
        connection.execute("INSERT INTO schedule_state VALUES(?,?)", (schedule["id"], due))
    enqueue(db, {}, schedule_key=f"{schedule['id']}:{due}")
    monkeypatch.setattr("app.scheduler.snapshot", lambda *args: {})
    tick(db)
    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        value = connection.execute("SELECT next_due FROM schedule_state").fetchone()[0]
    assert datetime.fromisoformat(value) > datetime.now(UTC)


@pytest.mark.asyncio
async def test_cancellation_during_final_case_skips_remaining_judges(tmp_path, monkeypatch):
    settings = Settings(
        data_dir=str(tmp_path), secret_key="a" * 40, admin_password="Strong-password!"
    )
    app = create_app(settings, start_worker=False)
    secret = cipher(settings).encrypt(b"secret").decode()
    criterion = {"name": "Clarity", "steps": ["Assess clarity."], "threshold": 0.7}
    saved = {
        "plan": {"fields": []},
        "service": {"kind": "demo"},
        "dataset": {"cases": [{"id": "one", "input": {"title": "A"}, "reference": {}}]},
        "provider": {
            "kind": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "x",
            "_secret": secret,
        },
        "criteria": [criterion, {**criterion, "name": "Second"}],
    }
    id = enqueue(app.state.db, saved)
    calls = []

    async def remote(*args, **kwargs):
        calls.append(1)
        with app.state.db.connect() as connection:
            connection.execute("UPDATE runs SET cancelled=1 WHERE id=?", (id,))
        return {"choices": [{"message": {"content": '{"score":8,"reason":"Clear"}'}}]}

    monkeypatch.setattr("app.judge.request_json", remote)
    await execute_run(app, id)
    assert len(calls) == 1
    assert read_run(app.state.db, id)["status"] == "cancelled"


def test_judge_mode_clears_hidden_reference_fields():
    plan = Plan(
        name="Judge",
        service_id="s",
        dataset_id="d",
        mode="judge",
        fields=[{"name": "subject", "output_path": "/subject", "reference_path": "/subject"}],
    )
    assert plan.fields == []


def test_comparison_key_tracks_measurement_changes_not_target_version():
    saved = {
        "dataset": {"id": "d", "version": 1},
        "plan": {
            "mode": "reference",
            "fields": [
                {
                    "name": "subject",
                    "output_path": "/subject",
                    "reference_path": "/subject",
                    "aliases": {},
                }
            ],
        },
        "criteria": [],
        "engine_versions": {"scikit-learn": "test"},
        "service": {"version": 1},
    }
    changed = deepcopy(saved)
    changed["service"]["version"] = 2
    assert comparison_key(changed) == comparison_key(saved)
    changed["plan"]["fields"][0]["output_path"] = "/labels"
    assert comparison_key(changed) != comparison_key(saved)
