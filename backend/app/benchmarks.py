"""Reference metrics: target errors remain in the primary denominator."""

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from .pointers import MISSING, get_pointer


def labels(value, aliases=None):
    if value is MISSING or value is None:
        return set()
    values = value if isinstance(value, list) else [value]
    if any(not isinstance(item, (str, int)) or isinstance(item, bool) for item in values):
        raise ValueError("Classification outputs must be strings, integers or lists of labels.")
    aliases = aliases or {}
    return {
        str(aliases.get(str(item).strip(), str(item).strip()))
        for item in values
        if str(item).strip()
    }


def scores(tp, fp, fn):
    # scikit-learn calculates standard binary metrics; null preserves undefined scores.
    truth = [1] * tp + [0] * fp + [1] * fn
    pred = [1] * tp + [1] * fp + [0] * fn
    if not truth:
        return {"precision": None, "recall": None, "f1": None}
    p, r, f, _ = precision_recall_fscore_support(truth, pred, average="binary", zero_division=0)
    return {
        "precision": float(p) if tp + fp else None,
        "recall": float(r) if tp + fn else None,
        "f1": float(f) if 2 * tp + fp + fn else None,
    }


def compare_fields(results: list[dict], specs: list[dict]) -> list[dict]:
    return [_compare(results, spec) for spec in specs]


def _compare(results, spec):
    pairs, successful = [], []
    for result in results:
        gold = get_pointer(result["reference"], spec["reference_path"])
        if gold is MISSING or gold is None:
            continue
        expected = labels(gold, spec.get("aliases"))
        actual = get_pointer(result.get("output"), spec["output_path"])
        pair = (expected, labels(actual, spec.get("aliases")))
        pairs.append(pair)
        if result["status"] == "success":
            successful.append(pair)
    universe = sorted(set().union(*(a | b for a, b in pairs))) if pairs else []
    classes = []
    for label in universe:
        tp = sum(label in a and label in b for a, b in pairs)
        fp = sum(label not in a and label in b for a, b in pairs)
        fn = sum(label in a and label not in b for a, b in pairs)
        classes.append(
            {"label": label, "support": tp + fn, "tp": tp, "fp": fp, "fn": fn, **scores(tp, fp, fn)}
        )
    tp, fp, fn = _counts(pairs)
    macro = {}
    for metric in ("precision", "recall", "f1"):
        values = [c[metric] if c[metric] is not None else 0 for c in classes if c["support"]]
        macro[metric] = float(np.mean(values)) if values else None
    return {
        "name": spec["name"],
        "annotated": len(pairs),
        "total": len(results),
        "coverage": len(pairs) / len(results) if results else 0,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "micro": scores(tp, fp, fn),
        "macro": macro,
        "successful_micro": scores(*_counts(successful)),
        "classes": classes,
    }


def _counts(pairs):
    return (
        sum(len(a & b) for a, b in pairs),
        sum(len(b - a) for a, b in pairs),
        sum(len(a - b) for a, b in pairs),
    )
