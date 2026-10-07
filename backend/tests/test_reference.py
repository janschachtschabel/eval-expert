import pytest

from app.benchmarks import compare_fields
from app.datasets import parse_dataset

SPEC = [{"name": "subject", "output_path": "/subject", "reference_path": "/subject"}]


def test_multilabel_counts_and_scores():
    results = [
        {
            "status": "success",
            "output": {"subject": ["math", "chemistry"]},
            "reference": {"subject": ["math", "physics"]},
        }
    ]
    report = compare_fields(results, SPEC)
    assert report[0]["micro"] == {"precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert report[0]["tp"] == report[0]["fp"] == report[0]["fn"] == 1


def test_errors_are_not_dropped_and_missing_gold_is_not_empty_gold():
    results = [
        {"status": "success", "output": {"subject": ["math"]}, "reference": {"subject": ["math"]}},
        {"status": "target_error", "output": None, "reference": {"subject": ["physics"]}},
        {"status": "success", "output": {"subject": ["math"]}, "reference": {}},
    ]
    report = compare_fields(results, SPEC)[0]
    assert report["annotated"] == 2
    assert report["coverage"] == pytest.approx(2 / 3)
    assert report["micro"]["recall"] == 0.5
    assert report["successful_micro"]["recall"] == 1


def test_aliases_deduplication_unknown_predictions_and_undefined_score():
    spec = [{**SPEC[0], "aliases": {"Mathematik": "math"}}]
    results = [
        {
            "status": "success",
            "output": {"subject": ["Mathematik", "math", "bogus"]},
            "reference": {"subject": ["math"]},
        }
    ]
    assert compare_fields(results, spec)[0]["fp"] == 1
    empty = [{"status": "success", "output": {"subject": []}, "reference": {"subject": []}}]
    assert compare_fields(empty, spec)[0]["micro"]["f1"] is None


def test_import_jsonl_and_csv_separates_reference():
    rows = parse_dataset(
        '{"id":"one","input":{"title":"A"},"reference":{"subject":["math"]}}', "jsonl"
    )
    assert rows[0]["input"] == {"title": "A"}
    csv = 'id,title,reference.subject\none,A,"math|physics"\n'
    rows = parse_dataset(csv, "csv")
    assert rows[0]["input"] == {"title": "A"}
    assert rows[0]["reference"]["subject"] == ["math", "physics"]


def test_bad_dataset_rejected_with_line_detail():
    with pytest.raises(ValueError, match="2"):
        parse_dataset('{"input":{},"reference":{}}\nnot-json', "jsonl")
