from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from . import run_queries
from .auth import current_user, editors
from .exports import stream_csv, stream_json, stream_report
from .models import RunStart
from .run_store import QueueFull, enqueue, list_runs, read_run, redact, snapshot

router = APIRouter(prefix="/runs")


def find(request, id):
    try:
        return read_run(request.app.state.db, id)
    except KeyError as error:
        raise HTTPException(404, "Run not found.") from error


@router.get("")
def list_all(request: Request, user=Depends(current_user)):
    return list_runs(request.app.state.db)


@router.post("")
def start(body: RunStart, request: Request, user=Depends(editors)):
    db = request.app.state.db
    try:
        saved = snapshot(db, body.plan_id)
        id = enqueue(db, saved)
    except QueueFull as error:
        raise HTTPException(409, str(error)) from error
    except (KeyError, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    db.audit(user["id"], "run.started", id)
    return read_run(db, id)


@router.get("/page")
def paged(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    comparison_key: str | None = Query(None, max_length=64),
    status: str | None = Query(None, max_length=32),
    user=Depends(current_user),
):
    return run_queries.page(request.app.state.db, limit, offset, comparison_key, status)


@router.get("/{id}/status")
def status(id: str, request: Request, user=Depends(current_user)):
    try:
        return run_queries.header(request.app.state.db, id, False)
    except KeyError as error:
        raise HTTPException(404, "Run not found.") from error


@router.get("/{id}/cases")
def cases(
    id: str,
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    status(id, request, user)
    return run_queries.cases(request.app.state.db, id, limit, offset)


@router.get("/{id}/cases/{ordinal}")
def case(id: str, ordinal: int, request: Request, user=Depends(current_user)):
    try:
        return run_queries.result(request.app.state.db, id, ordinal)
    except KeyError as error:
        raise HTTPException(404, "Case not found.") from error


@router.get("/{id}")
def detail(id: str, request: Request, user=Depends(current_user)):
    return find(request, id)


@router.post("/{id}/cancel", status_code=204)
def cancel(id: str, request: Request, user=Depends(editors)):
    find(request, id)
    with request.app.state.db.connect() as connection:
        connection.execute(
            "UPDATE runs SET cancelled=1 WHERE id=? AND status IN ('queued','running')", (id,)
        )
    request.app.state.db.audit(user["id"], "run.cancelled", id)


@router.post("/{id}/recompute")
def recompute(id: str, request: Request, user=Depends(editors)):
    db = request.app.state.db
    try:
        old = run_queries.header(db, id)
        old["snapshot"] = run_queries.frozen(db, id)["snapshot"]
    except KeyError as error:
        raise HTTPException(404, "Run not found.") from error
    if old["progress"] != old["total"] or old["status"] != "completed":
        raise HTTPException(422, "Only complete runs can reuse all responses.")
    try:
        saved = snapshot(db, old["snapshot"]["plan"]["id"])
    except (KeyError, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    if (
        saved["dataset"]["id"] != old["snapshot"]["dataset"]["id"]
        or saved["dataset"]["version"] != old["snapshot"]["dataset"]["version"]
    ):
        raise HTTPException(422, "Dataset changed; start a new target run.")
    saved["service"] = old["snapshot"]["service"]
    saved["plan"]["service_id"] = saved["service"]["id"]
    try:
        new = enqueue(db, saved, parent_id=id)
    except QueueFull as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    db.audit(user["id"], "run.recomputed", new)
    return read_run(db, new)


@router.get("/{id}/export")
def export(id: str, request: Request, format: str = "json", user=Depends(current_user)):
    run = find(request, id)
    if format not in ("csv", "json"):
        raise HTTPException(422, "Use csv or json.")
    rows = run_queries.iter_results(request.app.state.db, id, run["progress"])
    if format == "json":
        run["snapshot"] = redact(run_queries.frozen(request.app.state.db, id)["snapshot"])
    body = stream_csv(rows) if format == "csv" else stream_json(run, rows)
    return StreamingResponse(
        body,
        media_type="text/csv" if format == "csv" else "application/json",
        headers={"Content-Disposition": f'attachment; filename="eval-{id}.{format}"'},
    )


@router.get("/{id}/report")
def printable(id: str, request: Request, user=Depends(current_user)):
    run = find(request, id)
    return StreamingResponse(
        stream_report(run, run_queries.iter_results(request.app.state.db, id, run["progress"])),
        media_type="text/html",
    )
