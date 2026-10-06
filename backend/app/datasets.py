import csv
import io
import json


def parse_dataset(content: str, format: str) -> list[dict]:
    if len(content.encode("utf-8")) > 5_000_000:
        raise ValueError("Dataset exceeds 5 MB.")
    try:
        if format == "json":
            rows = json.loads(content)
        elif format == "jsonl":
            rows = []
            for number, line in enumerate(content.splitlines(), 1):
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError as error:
                        raise ValueError(f"Invalid JSON in line {number}.") from error
        elif format == "csv":
            rows = [_csv_row(row) for row in csv.DictReader(io.StringIO(content.lstrip("\ufeff")))]
        else:
            raise ValueError("Use json, jsonl or csv.")
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON at line {error.lineno}.") from error
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError("A dataset must contain 1–1000 cases.")
    seen = set()
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict) or not isinstance(row.get("input"), dict):
            raise ValueError(f"Case {number} requires an input object.")
        if not isinstance(row.get("reference", {}), dict):
            raise ValueError(f"Case {number} requires a reference object.")
        row["id"] = str(row.get("id") or number)
        row.setdefault("reference", {})
        if row["id"] in seen:
            raise ValueError(f"Duplicate case id: {row['id']}")
        seen.add(row["id"])
    return rows


def _csv_row(row):
    result = {"id": row.get("id"), "input": {}, "reference": {}}
    for key, value in row.items():
        if not key or key == "id":
            continue
        if key.startswith("reference."):
            # Empty cells mean missing annotation; [] is explicitly annotated empty.
            if value.strip():
                result["reference"][key[10:]] = [] if value == "[]" else value.split("|")
        else:
            result["input"][key.removeprefix("input.")] = value
    return result
