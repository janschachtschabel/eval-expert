"""Small persisted read models; large evidence is fetched only on demand."""

from .credentials import public_connection


def catalog_summary(kind, body):
    keep = (
        "name",
        "description",
        "kind",
        "url",
        "method",
        "model",
        "threshold",
        "mode",
        "dataset_id",
        "plan_id",
        "cron",
        "timezone",
        "enabled",
        "demo",
    )
    result = {k: body[k] for k in keep if k in body}
    if kind == "datasets":
        result["case_count"] = len(body.get("cases", []))
    return result


def run_models(saved):
    from .run_store import comparison_key, redact

    plan, dataset = saved.get("plan", {}), saved.get("dataset", {})
    configuration = {**saved, "dataset": {k: v for k, v in dataset.items() if k != "cases"}}
    configuration["dataset"]["case_count"] = len(dataset.get("cases", []))
    if "service" in configuration:
        configuration["service"] = public_connection(configuration["service"])
    brief = {
        "name": plan.get("name", ""),
        "plan_id": plan.get("id"),
        "plan_version": plan.get("version"),
        "dataset_id": dataset.get("id"),
        "dataset_version": dataset.get("version"),
        "mode": plan.get("mode"),
        "demo": dataset.get("demo", False),
        "total": len(dataset.get("cases", [])),
        "comparison_key": comparison_key(saved) if saved.get("engine_versions") else None,
    }
    return brief, redact(configuration)


def case_summary(result, ordinal):
    keep = (
        "case_id",
        "status",
        "target_duration_ms",
        "duration_ms",
        "reused_response",
        "error",
        "field_errors",
    )
    return {k: result[k] for k in keep if k in result} | {
        "ordinal": ordinal,
        "judge_count": len(result.get("judges", [])),
    }


def summary_brief(summary):
    return {
        **summary,
        "reference": [
            {
                **{k: v for k, v in field.items() if k != "classes"},
                "class_count": len(field.get("classes", [])),
            }
            for field in summary.get("reference", [])
        ],
    }
