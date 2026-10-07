import json

from app.database import Database
from app.migrations import migrate
from app.read_models import case_summary


def test_case_preview_is_useful_bounded_and_excludes_full_input():
    summary = case_summary(
        {"case_id": "one", "input": {"url": "https://example.org/", "secret": "private"}}, 0
    )
    assert summary["input_preview"] == "https://example.org/"
    assert "private" not in json.dumps(summary)
    assert len(case_summary({"input": {"title": "x" * 10000}}, 0)["input_preview"]) <= 240


def test_v3_upgrade_backfills_legacy_profile_and_case_without_changing_evidence(tmp_path):
    db = Database(tmp_path)
    profile = {
        "name": "Legacy",
        "mode": "judge",
        "service_id": "service",
        "dataset_id": "dataset",
        "provider_id": None,
        "criterion_ids": ["criterion"],
        "fields": [],
    }
    db.save_catalog("plans", profile, id="legacy")
    evidence = json.dumps(
        {"case_id": "url", "input": {"url": "https://example.org/"}, "output": {"text": "original"}}
    )
    with db.connect() as c:
        c.execute(
            "INSERT INTO runs(id,status,snapshot,created) "
            "VALUES('run','completed','{}','2026-10-07')"
        )
        c.execute("INSERT INTO results(run_id,ordinal,body) VALUES('run',0,?)", (evidence,))
        c.execute("UPDATE catalog SET list_body='{}'")
        c.execute("PRAGMA user_version=3")
    migrate(db)
    summary = db.list_catalog("plans")[0]
    assert summary["provider_id"] is None
    assert summary["criterion_ids"] == ["criterion"]
    assert summary["field_count"] == 0
    with db.connect() as c:
        assert c.execute("SELECT body FROM results").fetchone()[0] == evidence
        assert (
            json.loads(c.execute("SELECT brief FROM results").fetchone()[0])["input_preview"]
            == "https://example.org/"
        )
        assert c.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == 1
    migrate(db)
    assert db.list_catalog("plans")[0] == summary
