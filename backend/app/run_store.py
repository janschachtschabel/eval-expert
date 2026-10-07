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


def enqueue(db, saved, parent_id=None, schedule_key=None, max_bytes=50_000_000):
    from .read_models import run_models

    encoded = json.dumps(saved, ensure_ascii=False)
    size = len(encoded.encode())
    if size > max_bytes:
        raise ValueError("Run evidence budget exceeded by the configuration/dataset.")
    metadata, configuration = run_models(saved)
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
            """INSERT INTO runs(id,status,snapshot,created,parent_id,schedule_key,
            metadata,configuration,evidence_bytes)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                id,
                "queued",
                encoded,
                now(),
                parent_id,
                schedule_key,
                json.dumps(metadata),
                json.dumps(configuration),
                size,
            ),
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
    from .run_queries import cases, frozen, header, iter_results

    run = header(db, id)
    if internal:
        run["snapshot"] = frozen(db, id)["snapshot"]
        run["results"] = list(iter_results(db, id))
    else:
        listed = cases(db, id)
        run["results"] = listed["items"]
        run["results_total"] = listed["total"]
    return run


def list_runs(db):
    from .run_queries import page

    return page(db, limit=200)["items"]


def save_result(db, id, ordinal, result, max_bytes=50_000_000):
    from .read_models import case_summary

    encoded = json.dumps(result, ensure_ascii=False)
    size = len(encoded.encode())
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        updated = connection.execute(
            "UPDATE runs SET evidence_bytes=evidence_bytes+? WHERE id=? AND evidence_bytes+?<=?",
            (size, id, size, max_bytes),
        ).rowcount
        if not updated:
            raise ValueError("Run evidence budget exceeded; prior evidence is retained.")
        connection.execute(
            "INSERT INTO results(run_id,ordinal,body,brief) VALUES(?,?,?,?)",
            (id, ordinal, encoded, json.dumps(case_summary(result, ordinal), ensure_ascii=False)),
        )


def finish(db, id, status, summary):
    with db.connect() as connection:
        connection.execute(
            "UPDATE runs SET status=?,summary=?,finished=? WHERE id=?",
            (status, json.dumps(summary, allow_nan=False), now(), id),
        )
