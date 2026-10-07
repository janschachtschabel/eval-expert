import json

from app.auth import cipher
from app.config import Settings
from app.database import Database
from app.main import create_app
from app.run_queries import frozen, header, result


def test_v1_upgrade_preserves_evidence_versions_accounts_and_credentials(tmp_path):
    db = Database(tmp_path)
    service = {
        "id": "service",
        "version": 3,
        "name": "Legacy",
        "auth_header": "X-Team-Token",
        "auth_prefix": "",
        "headers": {"x-team-token": "legacy-credential", "Accept": "application/json"},
    }
    dataset = {
        "id": "dataset",
        "version": 2,
        "cases": [{"id": "case", "input": {"text": "x" * 100000}, "reference": {}}],
    }
    saved = {
        "service": service,
        "dataset": dataset,
        "plan": {"id": "plan", "version": 4, "name": "Legacy run", "mode": "reference"},
    }
    evidence = {
        "case_id": "case",
        "status": "success",
        "output": {"text": "original"},
        "judges": [],
    }
    db.save_catalog("services", service, id="service")
    db.save_catalog("datasets", dataset, id="dataset")
    with db.connect() as c:
        c.execute("INSERT INTO users VALUES('user','legacy-user','hash','viewer',1)")
        c.execute(
            "INSERT INTO runs(id,status,snapshot,created) VALUES(?,?,?,?)",
            ("run", "completed", json.dumps(saved), "2026-10-06"),
        )
        c.execute(
            "INSERT INTO results(run_id,ordinal,body) VALUES(?,?,?)",
            ("run", 0, json.dumps(evidence)),
        )
        c.execute("INSERT INTO schedule_state(id,next_due) VALUES('schedule','2026-10-08')")
        # Reproduce the original on-disk schema, before any v2 read models existed.
        c.execute("DROP INDEX runs_comparison")
        c.execute("DROP INDEX runs_queue")
        for table, column in [
            ("catalog", "list_body"),
            ("runs", "metadata"),
            ("runs", "configuration"),
            ("runs", "summary_brief"),
            ("runs", "evidence_bytes"),
            ("results", "brief"),
            ("schedule_state", "last_error"),
        ]:
            c.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        c.execute("PRAGMA user_version=1")
    settings = Settings(data_dir=str(tmp_path), secret_key="x" * 40, secure_cookie=False)
    app = create_app(settings, start_worker=False)
    upgraded = app.state.db
    assert header(upgraded, "run")["progress"] == 1
    assert "cases" not in header(upgraded, "run")["snapshot"]["dataset"]
    assert result(upgraded, "run", 0)["output"] == {"text": "original"}
    assert frozen(upgraded, "run")["snapshot"]["dataset"] == dataset
    assert upgraded.list_catalog("datasets")[0]["case_count"] == 1
    internal = upgraded.get_catalog("services", "service", internal=True)
    assert cipher(settings).decrypt(internal["_secret"].encode()).decode() == "legacy-credential"
    assert "legacy-credential" not in json.dumps(header(upgraded, "run"))
    with upgraded.connect() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 3
        assert (
            c.execute("SELECT username FROM users WHERE id='user'").fetchone()[0] == "legacy-user"
        )
        assert c.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == 2
        assert c.execute("SELECT next_due FROM schedule_state").fetchone()[0] == "2026-10-08"
    # Rerunning startup must not duplicate versions or change stored target evidence.
    again = create_app(settings, start_worker=False).state.db
    assert result(again, "run", 0) == result(upgraded, "run", 0)
    assert again.get_catalog("services", "service", internal=True) == internal
