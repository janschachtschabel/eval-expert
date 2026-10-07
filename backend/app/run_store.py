import hashlib
import json

from .database import new_id, now


class QueueFull(ValueError):
    pass


def snapshot(db, plan_id):
    plan = db.get_catalog("plans", plan_id)
    result = {
        "plan": plan,
        "service": db.get_catalog("services", plan["service_id"], True),
        "dataset": db.get_catalog("datasets", plan["dataset_id"]),
        "criteria": [],
    }
    if plan["mode"] != "judge" and not plan["fields"]:
        raise ValueError("Reference evaluations require at least one field.")
    if plan["mode"] != "reference":
        if not plan["provider_id"] or not plan["criterion_ids"]:
            raise ValueError("Judge evaluations require a provider and criteria.")
        result["provider"] = db.get_catalog("providers", plan["provider_id"], True)
        if not result["provider"].get("_secret"):
            raise ValueError("The judge provider requires an API key.")
        result["criteria"] = [db.get_catalog("criteria", id) for id in plan["criterion_ids"]]
    result["engine"] = {"reference": "scikit-learn", "judge": "DeepEval GEval"}
    import importlib.metadata

    result["engine_versions"] = {
        name: importlib.metadata.version(name) for name in ("scikit-learn", "deepeval")
    }
    from .benchmarks import labels
    from .pointers import get_pointer

    for case in result["dataset"]["cases"]:
        for field in plan["fields"]:
            try:
                labels(
                    get_pointer(case["reference"], field["reference_path"]), field.get("aliases")
                )
            except ValueError as error:
                raise ValueError(
                    f"Case {case['id']}, field {field['name']}: invalid reference labels."
                ) from error
    return result


def enqueue(db, saved, parent_id=None, schedule_key=None):
    id = new_id()
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        pending = connection.execute(
            "SELECT COUNT(*) FROM runs WHERE status IN ('queued','running')"
        ).fetchone()[0]
        if pending >= 20:
            raise QueueFull(
                "Queue limit reached (20 pending runs). Wait for completion or cancel runs."
            )
        connection.execute(
            """INSERT INTO runs(id,status,snapshot,created,parent_id,schedule_key)
            VALUES(?,?,?,?,?,?)""",
            (id, "queued", json.dumps(saved, ensure_ascii=False), now(), parent_id, schedule_key),
        )
    return id


def comparison_key(saved):
    provider = saved.get("provider", {})
    config = {
        "dataset": [saved["dataset"]["id"], saved["dataset"]["version"]],
        "mode": saved["plan"]["mode"],
        "fields": saved["plan"]["fields"],
        "criteria": [
            {
                k: c.get(k)
                for k in (
                    "id",
                    "version",
                    "steps",
                    "threshold",
                    "output_path",
                    "context_path",
                    "context_source",
                    "require_context",
                )
            }
            for c in saved["criteria"]
        ],
        "provider": {
            k: provider.get(k)
            for k in (
                "kind",
                "base_url",
                "model",
                "token_parameter",
                "max_tokens",
                "temperature",
                "json_mode",
            )
        },
        "engines": saved["engine_versions"],
    }
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def redact(value):
    if isinstance(value, dict):
        from .credentials import public_connection

        return {
            key: redact(
                public_connection(item) if key == "service" and isinstance(item, dict) else item
            )
            for key, item in value.items()
            if key not in ("_secret", "api_key")
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def read_run(db, id, internal=False):
    with db.connect() as connection:
        row = connection.execute("SELECT * FROM runs WHERE id=?", (id,)).fetchone()
        if not row:
            raise KeyError(id)
        cases = connection.execute(
            "SELECT body FROM results WHERE run_id=? ORDER BY ordinal", (id,)
        ).fetchall()
    run = dict(row)
    run["snapshot"], run["summary"] = json.loads(row["snapshot"]), json.loads(row["summary"])
    run["results"] = [json.loads(case["body"]) for case in cases]
    run["total"] = len(run["snapshot"]["dataset"]["cases"])
    run["progress"] = len(cases)
    if "engine_versions" in run["snapshot"]:
        run["comparison_key"] = comparison_key(run["snapshot"])
    return run if internal else redact(run)


def list_runs(db):
    with db.connect() as connection:
        rows = connection.execute("""SELECT r.*, COUNT(x.ordinal) AS progress FROM runs r
            LEFT JOIN results x ON r.id=x.run_id GROUP BY r.id
            ORDER BY r.created DESC LIMIT 200""").fetchall()
    result = []
    for row in rows:
        saved = json.loads(row["snapshot"])
        result.append(
            {
                key: row[key]
                for key in ("id", "status", "created", "finished", "progress", "parent_id")
            }
            | {
                "name": saved["plan"]["name"],
                "plan_id": saved["plan"]["id"],
                "plan_version": saved["plan"]["version"],
                "dataset_id": saved["dataset"]["id"],
                "dataset_version": saved["dataset"]["version"],
                "mode": saved["plan"]["mode"],
                "demo": saved["dataset"].get("demo", False),
                "total": len(saved["dataset"]["cases"]),
                "summary": json.loads(row["summary"]),
                "comparison_key": comparison_key(saved),
            }
        )
    return result


def save_result(db, id, ordinal, result):
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO results VALUES(?,?,?)",
            (id, ordinal, json.dumps(result, ensure_ascii=False)),
        )


def finish(db, id, status, summary):
    with db.connect() as connection:
        connection.execute(
            "UPDATE runs SET status=?,summary=?,finished=? WHERE id=?",
            (status, json.dumps(summary, allow_nan=False), now(), id),
        )
