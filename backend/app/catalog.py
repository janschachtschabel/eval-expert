from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from .auth import administrators, cipher, current_user, editors
from .datasets import parse_dataset
from .models import MODELS

router = APIRouter(prefix="/catalog")


def check_kind(kind):
    if kind not in MODELS:
        raise HTTPException(404, "Unknown resource.")


@router.get("/{kind}")
def list_items(kind: str, request: Request, user=Depends(current_user)):
    check_kind(kind)
    items = request.app.state.db.list_catalog(kind)
    if kind == "schedules":
        with request.app.state.db.connect() as connection:
            due = {
                row["id"]: row["next_due"]
                for row in connection.execute("SELECT * FROM schedule_state")
            }
        for item in items:
            item["next_due"] = due.get(item["id"])
    return items


@router.get("/{kind}/{id}")
def get_item(kind: str, id: str, request: Request, user=Depends(current_user)):
    check_kind(kind)
    try:
        return request.app.state.db.get_catalog(kind, id)
    except KeyError as error:
        raise HTTPException(404, "Resource not found.") from error


@router.get("/{kind}/{id}/versions")
def versions(kind: str, id: str, request: Request, user=Depends(current_user)):
    get_item(kind, id, request, user)
    import json

    from .credentials import public_connection

    with request.app.state.db.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM versions WHERE id=? ORDER BY version", (id,)
        ).fetchall()
    return [
        {
            "version": row["version"],
            "created": row["created"],
            "body": public_connection(json.loads(row["body"]))
            if kind == "services"
            else json.loads(row["body"]),
        }
        for row in rows
    ]


def save(kind, body, request, user, id=None):
    check_kind(kind)
    if kind in ("services", "providers") and user["role"] != "admin":
        raise HTTPException(403, "Administrator role required for connections.")
    if id:
        get_item(kind, id, request, user)
    body = dict(body)
    expected_version = body.get("version") if id else None
    if id and (type(expected_version) is not int or expected_version < 1):
        raise HTTPException(422, "An update requires the version you opened.")
    key = body.pop("api_key", None)
    if key is not None and (not isinstance(key, str) or len(key) > 4096):
        raise HTTPException(422, "Credentials must be a string of at most 4096 characters.")
    if kind == "datasets" and "content" in body:
        if not isinstance(body["content"], str):
            raise HTTPException(422, "Dataset content must be text.")
        try:
            body["cases"] = parse_dataset(body.pop("content"), body.pop("format", "jsonl"))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    try:
        model = MODELS[kind].model_validate(body)
        data = model.model_dump()
        if kind == "datasets":
            import json

            data["cases"] = parse_dataset(json.dumps(data["cases"]), "json")
        if kind == "schedules":
            from .scheduler import next_due

            next_due(data)
    except (ValidationError, ValueError) as error:
        message = str(error).split("For further")[0][:500]
        raise HTTPException(422, message) from error
    encrypted = None
    if key:
        encrypted = cipher(request.app.state.settings).encrypt(key.encode()).decode()
    if body.get("clear_secret"):
        encrypted = ""
    from .catalog_integrity import CatalogConflict

    try:
        item = request.app.state.db.save_catalog(kind, data, id, encrypted, expected_version, True)
    except CatalogConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    request.app.state.db.audit(user["id"], f"{kind}.saved", item["id"])
    return item


@router.post("/{kind}")
def create(kind: str, body: dict, request: Request, user=Depends(editors)):
    return save(kind, body, request, user)


@router.put("/{kind}/{id}")
def update(kind: str, id: str, body: dict, request: Request, user=Depends(editors)):
    return save(kind, body, request, user, id)


@router.delete("/{kind}/{id}", status_code=204)
def delete(kind: str, id: str, request: Request, user=Depends(administrators)):
    get_item(kind, id, request, user)
    from .catalog_integrity import CatalogInUse, delete_catalog

    try:
        delete_catalog(request.app.state.db, kind, id)
    except CatalogInUse as error:
        raise HTTPException(409, str(error)) from error
    request.app.state.db.audit(user["id"], f"{kind}.deleted", id)
