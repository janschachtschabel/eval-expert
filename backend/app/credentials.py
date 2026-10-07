"""Strip credentials from public connection configuration, including legacy data."""

import json


def public_connection(value):
    value = dict(value)
    forbidden = {
        "authorization",
        "cookie",
        "x-api-key",
        value.get("auth_header", "Authorization").lower(),
    }
    value["headers"] = {
        k: v for k, v in value.get("headers", {}).items() if k.lower() not in forbidden
    }
    value.pop("_secret", None)
    value.pop("api_key", None)
    return value


def migrate_credentials(db, settings):
    from .auth import cipher

    encryptor = cipher(settings)

    def secure(value, encrypted=None):
        header = value.get("auth_header", "Authorization")
        credential = next(
            (v for k, v in value.get("headers", {}).items() if k.lower() == header.lower()), None
        )
        clean = public_connection(value)
        encrypted = encrypted or value.get("_secret")
        if credential and not encrypted:
            prefix = value.get("auth_prefix", "Bearer ")
            if prefix and credential.startswith(prefix):
                credential = credential[len(prefix) :]
            else:
                clean["auth_prefix"] = ""
            encrypted = encryptor.encrypt(credential.encode()).decode()
        return clean, encrypted

    changed = False
    with db.connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS maintenance (name TEXT PRIMARY KEY)")
        if connection.execute(
            "SELECT 1 FROM maintenance WHERE name='credential_headers_v1'"
        ).fetchone():
            return
        connection.execute("PRAGMA secure_delete=ON")
        for row in connection.execute("SELECT id,body,secret FROM catalog WHERE kind='services'"):
            clean, encrypted = secure(json.loads(row["body"]), row["secret"])
            encoded = json.dumps(clean, ensure_ascii=False)
            changed |= encoded != row["body"] or encrypted != row["secret"]
            connection.execute(
                "UPDATE catalog SET body=?,secret=? WHERE id=?", (encoded, encrypted, row["id"])
            )
        for row in connection.execute(
            "SELECT rowid,body FROM versions WHERE json_type(body,'$.auth_header')='text'"
        ):
            clean = public_connection(json.loads(row["body"]))
            changed |= clean != json.loads(row["body"])
            connection.execute(
                "UPDATE versions SET body=? WHERE rowid=?",
                (json.dumps(clean, ensure_ascii=False), row["rowid"]),
            )
        for row in connection.execute("SELECT id,snapshot FROM runs"):
            saved = json.loads(row["snapshot"])
            if "service" not in saved:
                continue
            clean, encrypted = secure(saved["service"])
            if encrypted:
                clean["_secret"] = encrypted
            saved["service"] = clean
            encoded = json.dumps(saved, ensure_ascii=False)
            changed |= encoded != row["snapshot"]
            connection.execute("UPDATE runs SET snapshot=? WHERE id=?", (encoded, row["id"]))
            from .read_models import run_models

            metadata, configuration = run_models(saved)
            connection.execute(
                "UPDATE runs SET metadata=?,configuration=? WHERE id=?",
                (json.dumps(metadata), json.dumps(configuration), row["id"]),
            )
        connection.execute("INSERT INTO maintenance VALUES('credential_headers_v1')")
    if changed:
        with db.connect() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
