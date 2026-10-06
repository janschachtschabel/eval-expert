import asyncio
import logging
import time

from .auth import cipher
from .benchmarks import compare_fields, labels
from .database import now
from .judge import JudgeModel, evaluate
from .pointers import get_pointer
from .run_store import finish, read_run, save_result
from .scheduler import tick
from .target import call_target


def recover(db):
    with db.connect() as connection:
        connection.execute(
            "UPDATE runs SET status='interrupted',finished=? WHERE status='running'", (now(),)
        )


def decrypted(config, settings):
    value = config.get("_secret")
    return cipher(settings).decrypt(value.encode()).decode() if value else ""


def is_cancelled(db, id):
    if not id:
        return False
    with db.connect() as connection:
        return bool(
            connection.execute("SELECT cancelled FROM runs WHERE id=?", (id,)).fetchone()[0]
        )


async def execute_case(app, saved, case, reused=None, run_id=None):
    start = time.monotonic()
    result = {
        "case_id": case["id"],
        "input": case["input"],
        "reference": case["reference"],
        "output": None,
        "status": "success",
        "judges": [],
        "reused_response": reused is not None,
    }
    try:
        if reused is not None:
            result["output"] = reused["output"]
            result["status"] = reused["status"] if reused["status"] == "target_error" else "success"
            if result["status"] == "target_error":
                result["error"] = reused.get("error", "Original target request failed.")
                return result
        else:
            result["output"] = await call_target(
                saved["service"],
                case["input"],
                app.state.settings,
                decrypted(saved["service"], app.state.settings),
            )
        for spec in saved["plan"]["fields"]:
            labels(get_pointer(result["output"], spec["output_path"]), spec.get("aliases"))
    except Exception as error:
        result["status"] = "target_error"
        result["error"] = safe_error(error)
        result["output"] = None
    result["target_duration_ms"] = round((time.monotonic() - start) * 1000)
    if result["status"] == "success":
        for criterion in saved["criteria"]:
            if is_cancelled(app.state.db, run_id):
                break
            model = JudgeModel(
                saved["provider"],
                decrypted(saved["provider"], app.state.settings),
                app.state.settings,
            )
            try:
                verdict = await evaluate(model, criterion, case["input"], result["output"])
                result["judges"].append({**verdict, "status": "success"})
            except Exception as error:
                result["judges"].append(
                    {
                        "name": criterion["name"],
                        "status": "judge_error",
                        "error": safe_error(error),
                        "usage": model.usage,
                        "calls": model.calls,
                    }
                )
    result["duration_ms"] = round((time.monotonic() - start) * 1000)
    return result


def safe_error(error):
    # HTTP/auth response bodies are deliberately excluded; secrets must not enter reports.
    if isinstance(error, ValueError) and len(str(error)) < 200:
        return str(error)
    return f"{type(error).__name__}: evaluation failed; inspect endpoint/schema configuration."


def summarize(results, saved):
    verdicts = [j for result in results for j in result["judges"]]
    good = [j for j in verdicts if j["status"] == "success"]
    expected = len(results) * len(saved["criteria"])
    return {
        "reference": compare_fields(results, saved["plan"]["fields"]),
        "target_success_rate": sum(r["status"] == "success" for r in results) / len(results)
        if results
        else 0,
        "target_errors": sum(r["status"] != "success" for r in results),
        "judge": {
            "mean_score": sum(j["score"] for j in good) / len(good) if good else None,
            "pass_rate": sum(j["passed"] for j in good) / len(good) if good else None,
            "valid": len(good),
            "expected": expected,
            "coverage": len(good) / expected if expected else None,
            "errors": len(verdicts) - len(good),
        },
        "usage": {
            name: sum(j.get("usage", {}).get(name, 0) for j in verdicts)
            for name in ("prompt_tokens", "completion_tokens", "requests")
        },
    }


async def execute_run(app, id):
    db = app.state.db
    run = read_run(db, id, internal=True)
    with db.connect() as connection:
        claimed = connection.execute(
            "UPDATE runs SET status='running' WHERE id=? AND status='queued'", (id,)
        ).rowcount
    if not claimed:
        return
    saved = run["snapshot"]
    parent = read_run(db, run["parent_id"], True)["results"] if run["parent_id"] else None
    results = []
    for ordinal, case in enumerate(saved["dataset"]["cases"]):
        with db.connect() as connection:
            cancelled = connection.execute(
                "SELECT cancelled FROM runs WHERE id=?", (id,)
            ).fetchone()[0]
        if cancelled:
            break
        result = await execute_case(app, saved, case, parent[ordinal] if parent else None, id)
        save_result(db, id, ordinal, result)
        results.append(result)
    finish(db, id, "cancelled" if is_cancelled(db, id) else "completed", summarize(results, saved))


async def worker(app):
    db = app.state.db
    recover(db)
    last_tick = 0
    while True:
        if time.monotonic() - last_tick > 30:
            try:
                tick(db)
            except Exception as error:
                logging.getLogger(__name__).error("Scheduler failure: %s", type(error).__name__)
            last_tick = time.monotonic()
        with db.connect() as connection:
            row = connection.execute(
                "SELECT id FROM runs WHERE status='queued' ORDER BY created LIMIT 1"
            ).fetchone()
        if row:
            try:
                await execute_run(app, row["id"])
            except asyncio.CancelledError:
                raise
            except Exception as error:
                finish(db, row["id"], "failed", {"error": safe_error(error)})
        await asyncio.sleep(1)
