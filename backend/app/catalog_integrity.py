"""Catalog relationships checked within the mutation transaction."""

import json


class CatalogConflict(ValueError):
    pass


class CatalogInUse(ValueError):
    pass


def references(kind, body):
    if kind == "schedules":
        return [("plans", body["plan_id"])]
    if kind == "plans":
        refs = [("services", body["service_id"]), ("datasets", body["dataset_id"])]
        if body.get("provider_id"):
            refs.append(("providers", body["provider_id"]))
        refs.extend(("criteria", id) for id in body.get("criterion_ids", []))
        return refs
    return []


def validate_references(connection, kind, body):
    for target_kind, id in references(kind, body):
        if not connection.execute(
            "SELECT 1 FROM catalog WHERE kind=? AND id=?", (target_kind, id)
        ).fetchone():
            raise ValueError(f"Missing {target_kind} dependency: {id}")


def delete_catalog(db, kind, id):
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        used = []
        for row in connection.execute(
            "SELECT kind,body FROM catalog WHERE kind IN ('plans','schedules')"
        ):
            body = json.loads(row["body"])
            if (kind, id) in references(row["kind"], body):
                used.append(f"{row['kind']}: {body['name']}")
        if used:
            raise CatalogInUse("Resource is used by " + ", ".join(used))
        connection.execute("DELETE FROM catalog WHERE kind=? AND id=?", (kind, id))
        connection.execute("DELETE FROM schedule_state WHERE id=?", (id,))
