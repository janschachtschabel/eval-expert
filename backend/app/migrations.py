"""Idempotent SQLite upgrade; backfill one large row at a time."""

import json

from .read_models import case_summary, catalog_summary, run_models, summary_brief


def migrate(db):
    with db.connect() as c:
        if c.execute("PRAGMA user_version").fetchone()[0] >= 3:
            return
        c.execute("BEGIN IMMEDIATE")
        for table, column, definition in [
            ("catalog", "list_body", "TEXT NOT NULL DEFAULT '{}'"),
            ("runs", "metadata", "TEXT NOT NULL DEFAULT '{}'"),
            ("runs", "configuration", "TEXT NOT NULL DEFAULT '{}'"),
            ("runs", "summary_brief", "TEXT NOT NULL DEFAULT '{}'"),
            ("runs", "evidence_bytes", "INTEGER NOT NULL DEFAULT 0"),
            ("results", "brief", "TEXT NOT NULL DEFAULT '{}'"),
            ("schedule_state", "last_error", "TEXT"),
        ]:
            if column not in {row["name"] for row in c.execute(f"PRAGMA table_info({table})")}:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        for row in c.execute("SELECT id,kind,body FROM catalog"):
            c.execute(
                "UPDATE catalog SET list_body=? WHERE id=?",
                (json.dumps(catalog_summary(row["kind"], json.loads(row["body"]))), row["id"]),
            )
        for row in c.execute("SELECT id,snapshot,summary FROM runs"):
            metadata, configuration = run_models(json.loads(row["snapshot"]))
            size = (
                len(row["snapshot"].encode())
                + c.execute(
                    "SELECT COALESCE(SUM(LENGTH(CAST(body AS BLOB))),0) "
                    "FROM results WHERE run_id=?",
                    (row["id"],),
                ).fetchone()[0]
            )
            c.execute(
                "UPDATE runs SET metadata=?,configuration=?,evidence_bytes=?,summary_brief=? "
                "WHERE id=?",
                (
                    json.dumps(metadata),
                    json.dumps(configuration),
                    size,
                    json.dumps(summary_brief(json.loads(row["summary"]))),
                    row["id"],
                ),
            )
        for row in c.execute("SELECT run_id,ordinal,body FROM results"):
            c.execute(
                "UPDATE results SET brief=? WHERE run_id=? AND ordinal=?",
                (
                    json.dumps(case_summary(json.loads(row["body"]), row["ordinal"])),
                    row["run_id"],
                    row["ordinal"],
                ),
            )
        c.execute("CREATE INDEX IF NOT EXISTS runs_queue ON runs(status,created,id)")
        c.execute(
            "CREATE INDEX IF NOT EXISTS runs_comparison "
            "ON runs(json_extract(metadata,'$.comparison_key'),created,id)"
        )
        c.execute("PRAGMA user_version=3")
