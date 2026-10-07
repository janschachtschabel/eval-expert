"""Bounded run/history read paths, separate from complete streamed exports."""

import json


def header(db, id, configuration=True):
    columns = (
        "id,status,created,finished,parent_id,summary_brief AS summary,metadata,evidence_bytes"
    )
    if configuration:
        columns += ",configuration"
    with db.connect() as c:
        row = c.execute(
            f"SELECT {columns}, (SELECT COUNT(*) FROM results WHERE run_id=r.id) AS progress "
            "FROM runs r WHERE id=?",
            (id,),
        ).fetchone()
    if not row:
        raise KeyError(id)
    result = dict(row)
    result.update(json.loads(result.pop("metadata")))
    result["summary"] = json.loads(result["summary"])
    if configuration:
        result["snapshot"] = json.loads(result.pop("configuration"))
    return result


def page(db, limit=50, offset=0, comparison=None, status=None):
    clauses, args = [], []
    if comparison:
        clauses.append("json_extract(metadata,'$.comparison_key')=?")
        args.append(comparison)
    if status:
        clauses.append("status=?")
        args.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with db.connect() as c:
        total = c.execute("SELECT COUNT(*) FROM runs" + where, args).fetchone()[0]
        rows = c.execute(
            "SELECT id,status,created,finished,parent_id,summary_brief AS summary,"
            "metadata,evidence_bytes,"
            "(SELECT COUNT(*) FROM results WHERE run_id=r.id) AS progress FROM runs r"
            + where
            + " ORDER BY created DESC,id DESC LIMIT ? OFFSET ?",
            (*args, limit, offset),
        ).fetchall()
    items = []
    for row in rows:
        value = dict(row)
        value.update(json.loads(value.pop("metadata")))
        value["summary"] = json.loads(value["summary"])
        items.append(value)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def cases(db, id, limit=25, offset=0):
    with db.connect() as c:
        total = c.execute("SELECT COUNT(*) FROM results WHERE run_id=?", (id,)).fetchone()[0]
        rows = c.execute(
            "SELECT brief FROM results WHERE run_id=? ORDER BY ordinal LIMIT ? OFFSET ?",
            (id, limit, offset),
        ).fetchall()
    return {
        "items": [json.loads(row["brief"]) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def full_summary(db, id):
    with db.connect() as c:
        row = c.execute("SELECT summary FROM runs WHERE id=?", (id,)).fetchone()
    if not row:
        raise KeyError(id)
    return json.loads(row["summary"])


def classes(db, id, field, limit=50, offset=0):
    source = "FROM runs r JOIN json_each(r.summary,'$.reference') f "
    where = " WHERE r.id=? AND json_extract(f.value,'$.name')=?"
    with db.connect() as c:
        row = c.execute(
            "SELECT json_array_length(f.value,'$.classes') " + source + where, (id, field)
        ).fetchone()
        if row is None:
            raise KeyError(field)
        rows = c.execute(
            "SELECT l.value "
            + source
            + "JOIN json_each(f.value,'$.classes') l "
            + where
            + " ORDER BY CAST(l.key AS INTEGER) LIMIT ? OFFSET ?",
            (id, field, limit, offset),
        ).fetchall()
    return {
        "items": [json.loads(r[0]) for r in rows],
        "total": row[0] or 0,
        "limit": limit,
        "offset": offset,
    }


def result(db, id, ordinal, internal=False):
    from .run_store import redact

    with db.connect() as c:
        row = c.execute(
            "SELECT body FROM results WHERE run_id=? AND ordinal=?", (id, ordinal)
        ).fetchone()
    if not row:
        raise KeyError(ordinal)
    value = json.loads(row["body"])
    return value if internal else redact(value)


def iter_results(db, id, limit=None):
    from .run_store import redact

    last = -1
    while True:
        with db.connect() as c:
            rows = c.execute(
                "SELECT ordinal,body FROM results WHERE run_id=? AND ordinal>? AND ordinal<? "
                "ORDER BY ordinal LIMIT 5",
                (id, last, limit if limit is not None else 1000),
            ).fetchall()
        if not rows:
            return
        for row in rows:
            last = row["ordinal"]
            yield redact(json.loads(row["body"]))


def frozen(db, id):
    with db.connect() as c:
        row = c.execute("SELECT snapshot,parent_id,status FROM runs WHERE id=?", (id,)).fetchone()
    if not row:
        raise KeyError(id)
    return {**dict(row), "snapshot": json.loads(row["snapshot"])}
